import os
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from src.models import Video, Transcription, get_engine
from gestionar_subtitulos import traducir_srt_gemini, subir_srt_a_youtube, generar_descripcion_gemini, subir_descripcion_a_youtube
from src.gemini_refiner import GeminiRefiner
import logging
import time
import pickle
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from src.models import init_db
from dotenv import load_dotenv

load_dotenv()

# Configuración básica
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ManagerAPI")

# Inicializar DB con reintentos
max_retries = 10
for i in range(max_retries):
    try:
        init_db()
        logger.info("Database initialized successfully.")
        break
    except Exception as e:
        logger.warning(f"Database not ready yet, retrying in 5 seconds... ({i+1}/{max_retries})")
        time.sleep(5)


app = FastAPI(title="Zerf Subtitle Manager API")

# CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Google Drive (Cuenta de Audios)
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
TOKEN_DRIVE_PATH = "token_drive.pickle"

# Caché para el listado de Drive
drive_cache = {
    "files": [],
    "last_update": 0
}
CACHE_TTL = 300 # 5 minutos

def get_drive_service():
    """Obtiene el servicio de Google Drive usando el token específico de la cuenta de audios."""
    creds = None
    if os.path.exists(TOKEN_DRIVE_PATH):
        with open(TOKEN_DRIVE_PATH, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            logger.error("Credenciales de Drive no válidas. Ejecuta authorize_drive.py primero.")
            return None
    
    return build('drive', 'v3', credentials=creds)

def get_drive_srt_list():
    """Lista los archivos SRT en la carpeta configurada de Drive (con caché)."""
    global drive_cache
    if not DRIVE_FOLDER_ID:
        logger.warning("DRIVE_FOLDER_ID no configurado en .env")
        return []
    
    # Usar caché si es reciente
    now = time.time()
    if now - drive_cache["last_update"] < CACHE_TTL and drive_cache["files"]:
        logger.info("Usando lista de Drive desde caché.")
        return drive_cache["files"]
    
    service = get_drive_service()
    if not service:
        return []
    
    try:
        query = f"'{DRIVE_FOLDER_ID}' in parents and (name contains '.srt' or mimeType = 'text/plain') and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=1000,
            fields="files(id, name)"
        ).execute()
        files = results.get('files', [])
        logger.info(f"Encontrados {len(files)} archivos en la carpeta de Drive.")
        
        # Actualizar caché
        drive_cache["files"] = files
        drive_cache["last_update"] = now
        return files
    except Exception as e:
        logger.error(f"Error listando archivos de Drive: {e}")
        return drive_cache["files"] # Devolver vieja si falla

def get_drive_file_content(file_id):
    """Descarga el contenido de un archivo de Drive."""
    service = get_drive_service()
    if not service:
        return None
    try:
        content = service.files().get_media(fileId=file_id).execute()
        return content.decode('utf-8')
    except Exception as e:
        logger.error(f"Error descargando archivo de Drive {file_id}: {e}")
        return None

def ensure_local_audio(youtube_id):
    """Verifica si el audio MP3 existe localmente. Si no, intenta descargarlo de Drive."""
    audio_dir = os.path.join(os.getcwd(), "output", "Transcripts_Video", "AUDIO_MP3")
    os.makedirs(audio_dir, exist_ok=True)
    
    # 1. Comprobar localmente
    for fname in os.listdir(audio_dir):
        if youtube_id in fname and fname.endswith(".mp3"):
            return os.path.join(audio_dir, fname)
            
    # 2. Buscar en Drive
    if not DRIVE_FOLDER_ID:
        return None
        
    service = get_drive_service()
    if not service:
        return None
        
    try:
        # Buscamos archivos que contengan el youtube_id en la carpeta de audios
        query = f"'{DRIVE_FOLDER_ID}' in parents and name contains '{youtube_id}' and (name contains '.mp3' or mimeType = 'audio/mpeg') and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        # FALLBACK: Si no está en esa carpeta, buscar en TODO el Drive del usuario
        if not files:
            logger.info(f"Audio no encontrado en carpeta primaria. Buscando en todo el Drive para {youtube_id}...")
            query_global = f"name contains '{youtube_id}' and (name contains '.mp3' or mimeType = 'audio/mpeg') and trashed = false"
            results = service.files().list(q=query_global, fields="files(id, name)").execute()
            files = results.get('files', [])

        if not files:
            logger.warning(f"Audio no encontrado en Drive para {youtube_id}")
            return None
            
        file_id = files[0]['id']
        file_name = files[0]['name']
        dest_path = os.path.join(audio_dir, file_name)
        
        logger.info(f"Descargando audio de Drive: {file_name}...")
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        with open(dest_path, 'wb') as f:
            f.write(fh.getvalue())
            
        logger.info(f"✅ Audio descargado en: {dest_path}")
        return dest_path
        
    except Exception as e:
        logger.error(f"Error descargando audio de Drive para {youtube_id}: {e}")
        return None

# Directorios de datos (Mantener para local/legacy)
SRT_DIR_WINDOWS = "G:\\Mi unidad\\Transcripts_Barca\\SRT_YouTube"
SRT_DIR_DOCKER = "/subtitles_drive"
SRT_DIR = SRT_DIR_DOCKER if os.path.exists(SRT_DIR_DOCKER) else SRT_DIR_WINDOWS
YOUTUBE_SUBS_DIR = os.path.join(os.getcwd(), "youtube_subs")
VIDEO_LIST_JSON = "video_list.json"

# DB Session
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@app.get("/compare")
def compare_view(v: str):
    """Sirve la página de comparación para un vídeo."""
    return FileResponse("test_materials/subtitles_compare.html")

@app.get("/localizations")
def localizations_view(v: str):
    """Sirve la página dedicada de Gestión de Localizaciones para un vídeo."""
    return FileResponse("test_materials/localizations_view.html")

@app.get("/api/videos")
def list_videos(skip: int = 0, limit: int = 25, gemini: str = "all"):
    """Obtiene vídeos de la base de datos que tienen SRT, ordenados por fecha y paginados."""
    db = SessionLocal()
    from sqlalchemy import and_, or_
    try:
        # Extraemos todos los vídeos
        query = db.query(Video).outerjoin(
            Transcription, 
            and_(Video.id == Transcription.video_id, Transcription.language == 'es')
        )
        
        if gemini == 'yes':
            query = query.filter(Transcription.refinado_srt != None, Transcription.refinado_srt != "")
        elif gemini == 'no':
            query = query.filter(or_(Transcription.refinado_srt == None, Transcription.refinado_srt == ""))

        query = query.order_by(Video.upload_date.desc())
        
        total = query.count()
        videos = query.offset(skip).limit(limit).all()
        
        result = []
        for v in videos:
            # Info de otros idiomas
            other_langs = []
            for t in v.transcriptions:
                if t.language != 'es':
                    other_langs.append({
                        "lang": t.language,
                        "uploaded": bool(t.srt_uploaded_at)
                    })
            
            result.append({
                "id": v.id,
                "youtube_id": v.youtube_id,
                "title": v.title,
                "description": "", 
                "channel": v.channel or "",
                "duration": v.duration,
                "duration_string": v.duration_string or "",
                "tags": v.tags or "",
                "category": v.category or "",
                "is_live": v.is_live,
                "status": v.status,
                "published_at": v.upload_date.isoformat() if v.upload_date else None,
                "thumbnail": v.thumbnail,
                "has_srt": bool(v.transcription and v.transcription.srt_content),
                "has_vtt": bool(v.transcription and v.transcription.vtt),
                "has_gemini": bool(v.transcription and v.transcription.refinado_srt and v.transcription.refinado_srt.strip()),
                "srt_uploaded_at": v.transcription.srt_uploaded_at.isoformat() if (v.transcription and v.transcription.srt_uploaded_at) else None,
                "metadata_updated_at": v.metadata_updated_at.isoformat() if v.metadata_updated_at else None,
                "other_languages": other_langs
            })
            
        return {"total": total, "videos": result, "skip": skip, "limit": limit}
    except Exception as e:
        logger.error(f"Error en list_videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/missing-vtt-count")
@app.get("/api/stats-v2")
def stats_v2():
    """
    Devuelve las estadísticas de la base de datos.
    Soporta múltiples nombres de campos para evitar errores 'undefined' por caché del navegador.
    """
    db = SessionLocal()
    try:
        total = db.query(Video).count()
        with_vtt = db.query(Video).join(Video.transcription).filter(
            Transcription.vtt != None, Transcription.vtt != ""
        ).count()
        with_srt = db.query(Video).join(Video.transcription).filter(
            Transcription.srt_content != None, Transcription.srt_content != ""
        ).count()
        
        stats = {
            "total": total,
            "with_vtt": with_vtt,
            "whisper_count": with_srt,
            "with_srt": with_srt, # Clave redundante para retrocompatibilidad
            "missing": total - with_vtt
        }
        return stats
    finally:
        db.close()

@app.post("/api/translate/{youtube_id}/{lang}")
def translate_video(youtube_id: str, lang: str, background_tasks: BackgroundTasks):
    """Lanza la traducción de un vídeo en segundo plano."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        # Obtener contenido SRT
        srt_content = None
        if video.transcription:
            srt_content = video.transcription.srt_content
        
        if not srt_content:
            # Intentar leer de disco
            if os.path.isdir(SRT_DIR):
                for f in os.listdir(SRT_DIR):
                    if youtube_id in f:
                        with open(os.path.join(SRT_DIR, f), 'r', encoding='utf-8') as srt_f:
                            srt_content = srt_f.read()
                        break
        
        # Intentar fallback a otros campos
        if not srt_content and video.transcription:
            srt_content = video.transcription.whisper_srt or video.transcription.temp_refinado_srt or video.transcription.whisper_text

        if not srt_content:
            logger.error(f"Traducción abortada para {youtube_id}: No hay ningún SRT disponible en BD o disco.")
            raise HTTPException(status_code=400, detail="No hay SRT disponible para traducir")

        logger.info(f"Traducción autorizada. Iniciando worker en background para {youtube_id} a idioma {lang}...")

        #worker
        def do_translate():
            try:
                logger.info(f"--- INICIO TRADUCCIÓN BACKGROUND: {youtube_id} -> {lang} ---")
                
                # 1. Traducir el SRT
                translated_srt = traducir_srt_gemini(srt_content, lang)
                
                # 2. Traducir Título y Descripción
                original_title = video.title or ""
                original_desc = video.description or ""
                
                translated_meta = {}
                if original_title and original_desc:
                    try:
                        from gestionar_subtitulos import traducir_metadatos_gemini
                        translated_meta = traducir_metadatos_gemini(original_title, original_desc, lang)
                    except Exception as meta_e:
                        logger.error(f"Error traduciendo metadatos: {meta_e}")
                
                # 3. Guardar en Base de Datos
                # Necesitamos nueva sesión para el hilo en background
                from src.models import get_engine
                from sqlalchemy.orm import sessionmaker
                engine_bg = get_engine()
                SessionBg = sessionmaker(bind=engine_bg)
                db_bg = SessionBg()
                
                try:
                    v_bg = db_bg.query(Video).filter_by(youtube_id=youtube_id).first()
                    
                    # Buscar si ya existe una transcripción en este idioma
                    existing_t = db_bg.query(Transcription).filter_by(video_id=v_bg.id, language=lang).first()
                    
                    if existing_t:
                        existing_t.refinado_srt = translated_srt
                        existing_t.srt_content = translated_srt
                        existing_t.translated_title = translated_meta.get("title")
                        existing_t.translated_description = translated_meta.get("description")
                    else:
                        new_t = Transcription(
                            video_id=v_bg.id,
                            language=lang,
                            refinado_srt=translated_srt,
                            srt_content=translated_srt, # Mantenemos ambos por legacy
                            translated_title=translated_meta.get("title"),
                            translated_description=translated_meta.get("description")
                        )
                        db_bg.add(new_t)
                    
                    db_bg.commit()
                    logger.info("Traducción guardada en Base de Datos local.")
                    
                    # 4. Subir a YouTube (Subtítulos + Metadatos)
                    try:
                        from gestionar_subtitulos import subir_srt_a_youtube, subir_localizacion_a_youtube
                        
                        logger.info("Iniciando subida a YouTube...")
                        # SRT
                        subir_srt_a_youtube(youtube_id, translated_srt, lang)
                        
                        # Metadatos (Localización)
                        if translated_meta and 'title' in translated_meta and 'description' in translated_meta:
                            subir_localizacion_a_youtube(
                                youtube_id, 
                                lang, 
                                translated_meta['title'], 
                                translated_meta['description']
                            )
                        logger.info("✅ Todo subido a YouTube con éxito.")
                        
                        # Registrar la subida en la BD
                        try:
                            from datetime import datetime
                            if 'new_t' in locals() and new_t:
                                new_t.srt_uploaded_at = datetime.utcnow()
                            elif 'existing_t' in locals() and existing_t:
                                existing_t.srt_uploaded_at = datetime.utcnow()
                            db_bg.commit()
                            logger.info("Fecha de subida registrada tras traducción.")
                        except Exception as db_e2:
                            logger.error(f"Error registrando srt_uploaded_at tras traducción: {db_e2}")
                        
                    except Exception as yt_e:
                        logger.error(f"Subida a YouTube completada con errores: {yt_e}")
                        
                finally:
                    db_bg.close()
                    
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                logger.error(f"Error crítico en proceso de traducción para {youtube_id}:\n{error_trace}")

        background_tasks.add_task(do_translate)
        return {"status": "started", "message": f"Traducción y Subida a {lang} iniciada"}
    finally:
        db.close()

@app.post("/api/upload/{youtube_id}/{lang}")
def upload_video(youtube_id: str, lang: str, background_tasks: BackgroundTasks):
    """Sube un subtítulo a YouTube."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video:
             raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        # --- STRICT DATABASE-ONLY LOGIC ---
        from src.models import Transcription
        trans = db.query(Transcription).filter_by(video_id=video.id, language=lang).first()
        
        srt_content = None
        if trans:
            # PRIORIDAD: Refinado definitivo, luego borrador temporal, luego original
            srt_content = trans.refinado_srt or trans.temp_refinado_srt or trans.srt_content
            
            # Fallback especial para español si no hay nada en los campos anteriores
            if not srt_content and lang == 'es':
                srt_content = trans.whisper_srt
        
        if not srt_content:
            raise HTTPException(status_code=400, detail=f"No se encontró contenido en la Base de Datos para el idioma: {lang}. Por favor, genera o guarda el subtítulo antes de subir.")

        def do_upload():
            try:
                subir_srt_a_youtube(youtube_id, srt_content, lang)
                logger.info(f"Subida completada para {youtube_id} ({lang})")
                # Guardar fecha de subida en la BD
                db2 = SessionLocal()
                try:
                    from src.models import Transcription
                    video2 = db2.query(Video).filter_by(youtube_id=youtube_id).first()
                    if video2:
                        trans2 = db2.query(Transcription).filter_by(video_id=video2.id, language=lang).first()
                        if trans2:
                            from datetime import datetime
                            trans2.srt_uploaded_at = datetime.utcnow()
                            db2.commit()
                            logger.info(f"srt_uploaded_at guardado para {youtube_id} ({lang})")
                except Exception as db_e:
                    logger.error(f"Error guardando srt_uploaded_at: {db_e}")
                finally:
                    db2.close()
            except Exception as e:
                logger.error(f"Error subiendo a YouTube: {e}")

        background_tasks.add_task(do_upload)
        return {"status": "started", "message": f"Subida de {lang} iniciada"}
    finally:
        db.close()

@app.delete("/api/delete-yt-caption/{youtube_id}/{lang}")
def delete_yt_caption(youtube_id: str, lang: str):
    """Elimina un subtítulo de YouTube y actualiza la BD local."""
    from gestionar_subtitulos import borrar_srt_de_youtube
    
    success = borrar_srt_de_youtube(youtube_id, lang)
    if success:
        # Actualizar BD para marcar como no-subido
        db = SessionLocal()
        try:
            video = db.query(Video).filter_by(youtube_id=youtube_id).first()
            if video:
                trans = db.query(Transcription).filter_by(video_id=video.id, language=lang).first()
                if trans:
                    trans.srt_uploaded_at = None
                    db.commit()
            return {"status": "success", "message": f"Subtítulo {lang} eliminado de YouTube y BD."}
        finally:
            db.close()
    else:
        return {"status": "error", "message": f"No se pudo eliminar el subtítulo {lang} de YouTube."}

@app.get("/api/videos/{youtube_id}")
def get_video_detail(youtube_id: str):
    """Obtiene los detalles completos de un vídeo."""
    db = SessionLocal()
    try:
        v = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not v:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        return {
            "id": v.id,
            "youtube_id": v.youtube_id,
            "title": v.title,
            "description": v.description or "",
            "channel": v.channel or "",
            "duration": v.duration,
            "duration_string": v.duration_string or "",
            "tags": v.tags or "",
            "category": v.category or "",
            "is_live": v.is_live,
            "status": v.status,
            "thumbnail": v.thumbnail,
            "published_at": v.upload_date.isoformat() if v.upload_date else None
        }
    finally:
        db.close()

@app.get("/api/videos/{youtube_id}/localizations")
def get_video_localizations(youtube_id: str):
    """Devuelve todos los idiomas traducidos disponibles para un vídeo y sus metadatos."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
            
        langs = []
        for t in video.transcriptions:
            if t.language != 'es':
                langs.append({
                    "language": t.language,
                    "translated_title": t.translated_title,
                    "translated_description": t.translated_description,
                    "has_srt": bool(t.refinado_srt or t.srt_content),
                    "srt_uploaded_at": t.srt_uploaded_at.isoformat() if t.srt_uploaded_at else None,
                    "uploaded": bool(t.srt_uploaded_at)
                })
        return {"localizations": langs}
    finally:
        db.close()

@app.post("/api/videos/{youtube_id}/description")
def update_video_description(youtube_id: str, data: dict):
    """Guarda la descripción editada manualmente en la DB."""
    db = SessionLocal()
    try:
        v = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not v:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        v.description = data.get("description", "")
        db.commit()
        return {"status": "success", "message": "Descripción guardada en DB"}
    finally:
        db.close()

@app.put("/api/videos/{youtube_id}")
def update_video_full(youtube_id: str, data: dict):
    """Actualiza todos los campos editables del vídeo."""
    db = SessionLocal()
    try:
        v = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not v:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        if "title" in data: v.title = data["title"]
        if "description" in data: v.description = data["description"]
        if "tags" in data: v.tags = data["tags"]
        if "category" in data: v.category = data["category"]
        if "channel" in data: v.channel = data["channel"]
        if "duration_string" in data: v.duration_string = data["duration_string"]
        if "thumbnail" in data: v.thumbnail = data["thumbnail"]
        db.commit()
        return {"status": "success", "message": "Vídeo actualizado en DB"}
    finally:
        db.close()

@app.post("/api/videos/{youtube_id}/generate-description")
def generate_video_description(youtube_id: str):
    """Genera una descripción usando Gemini basada en el SRT."""
    db = SessionLocal()
    try:
        v = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not v:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        # Obtener SRT
        srt_content = None
        if v.transcription:
            srt_content = v.transcription.srt_content
        
        if not srt_content:
            # Fallback a local
            target_file = f"SRT_es_{youtube_id}.srt"
            if os.path.exists(target_file):
                with open(target_file, "r", encoding="utf-8") as f:
                    srt_content = f.read()
        
        if not srt_content:
            raise HTTPException(status_code=400, detail="No hay SRT para generar la descripción")
        
        ai_description = generar_descripcion_gemini(srt_content)
        
        # Guardar en DB (opcional, pero mejor que el usuario la vea antes)
        return {"status": "success", "description": ai_description}
    finally:
        db.close()

@app.post("/api/videos/{youtube_id}/upload-description")
def upload_video_description(youtube_id: str, background_tasks: BackgroundTasks):
    """Sube la descripción actual en DB a YouTube."""
    db = SessionLocal()
    try:
        v = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not v or not v.description:
            raise HTTPException(status_code=404, detail="Vídeo o descripción no encontrados")

        def do_upload():
            try:
                subir_descripcion_a_youtube(youtube_id, v.description)
                logger.info(f"Descripción subida a YT para {youtube_id}")
            except Exception as e:
                logger.error(f"Error subiendo descripción a YT: {e}")

        background_tasks.add_task(do_upload)
        return {"status": "started", "message": "Subida de descripción iniciada"}
    finally:
        db.close()

@app.post("/api/sync-metadata/{youtube_id}")
def sync_metadata(youtube_id: str, background_tasks: BackgroundTasks):
    """Enriquece los metadatos de un vídeo específico."""
    from sync_srt_to_db import fetch_metadata, enriquecer_video
    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")

        def do_sync():
            try:
                logger.info(f"Sincronizando metadatos para {youtube_id}...")
                info = fetch_metadata(youtube_id)
                if info:
                    # Usar una nueva sesión para el hilo de fondo
                    from src.models import get_engine
                    import sqlalchemy.orm
                    engine_sync = get_engine()
                    SessionSync = sqlalchemy.orm.sessionmaker(bind=engine_sync)
                    db_sync = SessionSync()
                    try:
                        v_sync = db_sync.query(Video).filter_by(youtube_id=youtube_id).first()
                        enriquecer_video(db_sync, v_sync, info)
                        db_sync.commit()
                        logger.info(f"Metadatos sincronizados ✅ para {youtube_id}")
                    finally:
                        db_sync.close()
            except Exception as e:
                logger.error(f"Error sincronizando metadatos: {e}")

        background_tasks.add_task(do_sync)
        return {"status": "started", "message": "Sincronización iniciada"}
    finally:
        db.close()

@app.get("/api/subtitles/vtt/{youtube_id}")
def get_vtt_content(youtube_id: str):
    """Busca y sirve el contenido VTT de YouTube."""
    # 1. Buscar en carpetas conocidas
    search_dirs = [YOUTUBE_SUBS_DIR, os.getcwd()]
    for d in search_dirs:
        if not os.path.exists(d): continue
        for lang in ['es', 'en']:
            fname = f"{youtube_id}.{lang}.vtt"
            path = os.path.join(d, fname)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return {"content": f.read(), "filename": fname}
    
    raise HTTPException(status_code=404, detail="VTT no encontrado")

@app.get("/api/subtitles/srt/{youtube_id}")
def get_srt_content_api(youtube_id: str):
    """Busca y sirve el contenido SRT (refinado/fusionado)."""
    db = SessionLocal()
    try:
        # 1. Prioridad: Base de Datos
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if video and video.transcription and video.transcription.srt_content:
            return {"content": video.transcription.srt_content, "source": "db"}

        # 2. Archivos locales (traducciones recientes o temporales)
        local_files = [
            f"SRT_en_{youtube_id}.srt",
            f"SRT_es_{youtube_id}.srt",
            f"temp_upload_{youtube_id}.srt"
        ]
        for f in local_files:
            if os.path.exists(f):
                with open(f, 'r', encoding='utf-8') as srt_f:
                    return {"content": srt_f.read(), "source": "local"}

        # 3. Drive API
        drive_files = get_drive_srt_list()
        for f in drive_files:
            if youtube_id in f['name']:
                content = get_drive_file_content(f['id'])
                if content:
                    return {"content": content, "source": "drive_api"}

        # 4. Carpeta de Drive Local (Legacy)
        if os.path.isdir(SRT_DIR):
            for f in os.listdir(SRT_DIR):
                if youtube_id in f:
                    with open(os.path.join(SRT_DIR, f), 'r', encoding='utf-8') as srt_f:
                        return {"content": srt_f.read(), "source": "drive_local"}

        raise HTTPException(status_code=404, detail="SRT no encontrado")
    finally:
        db.close()

from pydantic import BaseModel
class SRTUpdate(BaseModel):
    temp_srt: str = None
    refined_srt: str = None

@app.get("/api/refine/{youtube_id}")
def refine_srt_api(youtube_id: str):
    """Refina el SRT original con Gemini. Si hay audio local, usa refinamiento multimodal."""
    db = SessionLocal()
    srt_content = None
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        if video.transcription and video.transcription.srt_content:
            srt_content = video.transcription.srt_content
            
        if not srt_content:
            raise HTTPException(status_code=400, detail="No hay SRT original para refinar")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
        
    # Paso 1: Asegurar audio (Local o Drive)
    audio_path = ensure_local_audio(youtube_id)
    
    # MODO HÍBRIDO: Intentamos audio, si falla avisamos pero seguimos con texto
    if not audio_path:
        logger.warning(f"⚠️ Refinamiento MULTIMODAL NO DISPONIBLE para {youtube_id}. Procediendo solo con TEXTO.")
        # No lanzamos 400, dejamos que pase con audio_path=None

    try:
        logger.info(f"Iniciando proceso experto con Gemini 2.5 Pro para {youtube_id}...")
        
        # Cargamos el diccionario desde JSON
        try:
            with open("data/diccionario.json", "r", encoding="utf-8") as dict_f:
                dictionary = json.load(dict_f)
        except:
            dictionary = {}

        match_context = f"Título: {video.title}\nDescripción: {video.description}"

        refiner = GeminiRefiner()
        refined_srt = refiner.refine_transcription(
            base_text=srt_content,
            audio_path=audio_path,
            dictionary=dictionary,
            match_context=match_context
        )
        
        # SI GEMINI NO DEVUELVE NADA O FALLA EL AUDIO
        if not refined_srt:
            raise HTTPException(status_code=500, detail="Gemini 2.5 Pro no pudo procesar el audio correctamente.")

        # LIMPÌEZA: Borrar audio local tras el éxito (Requisito del usuario)
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"🧹 Audio local eliminado para ahorrar espacio: {os.path.basename(audio_path)}")
            except:
                pass
        
        return {"refined_raw": refined_srt}
    except Exception as e:
        logger.error(f"Error refinando: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save-temp/{youtube_id}")
def save_temp_srt_api(youtube_id: str, data: SRTUpdate):
    """Guarda el borrador temporal de la edición."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video or not video.transcription:
            raise HTTPException(status_code=404, detail="Transcipción no encontrada")
        
        if data.temp_srt is not None:
            video.transcription.temp_refinado_srt = data.temp_srt
            db.commit()
            return {"success": True}
        return {"success": False, "error": "No data"}
    finally:
        db.close()

@app.post("/api/save-final/{youtube_id}")
def save_final_srt_api(youtube_id: str, data: SRTUpdate):
    """Guarda la edición definitiva (y borra la temporal si existe)."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video or not video.transcription:
            raise HTTPException(status_code=404, detail="Transcipción no encontrada")
        
        if data.refined_srt is not None:
            video.transcription.refinado_srt = data.refined_srt
            video.transcription.temp_refinado_srt = None # Limpiar borrador al guardar definitivo
            db.commit()
            return {"success": True}
        return {"success": False, "error": "No data"}
    finally:
        db.close()

@app.get("/api/subtitles/all/{youtube_id}")
def get_all_subtitles(youtube_id: str):
    """Obtiene los tres tipos de subtítulos para comparar: VTT, Whisper y Refinado."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        t = video.transcription
        return {
            "vtt": t.vtt if t else None,
            "whisper_srt": t.whisper_srt if t else None,
            "temp_refinado_srt": t.temp_refinado_srt if t else None,
            "refinado_srt": t.refinado_srt if t else None,
            "srt_uploaded_at": t.srt_uploaded_at.isoformat() if (t and t.srt_uploaded_at) else None
        }
    finally:
        db.close()

# Removed FastAPI subtitles/all (redundant for PHP version)

@app.post("/api/sync-new-videos")
def sync_new_videos_api(background_tasks: BackgroundTasks):
    """Ejecuta el script de sincronización de YouTube a la DB."""
    def do_sync():
        try:
            import subprocess
            logger.info("Iniciando búsqueda de nuevos vídeos...")
            subprocess.run(["python", "scripts/database/sync_youtube_to_db.py"], check=True)
            logger.info("Búsqueda de vídeos completada ✅")
        except Exception as e:
            logger.error(f"Error comprobando nuevos vídeos: {e}")

    background_tasks.add_task(do_sync)
    return {"status": "started", "message": "Buscando nuevos vídeos..."}

@app.post("/api/refine-advanced/{youtube_id}")
def refine_advanced(youtube_id: str):
    """
    Refinamiento avanzado multimodal (SINCRÓNICO):
    1. Busca el audio en Drive.
    2. Usa Gemini 2.5 Pro con el vídeo/audio para corregir el SRT.
    3. Actualiza la BD y devuelve el resultado.
    """
    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
        logger.info(f"--- INICIANDO REFINAMIENTO AVANZADO SINCRÓNICO: {youtube_id} ---")
        refiner = GeminiRefiner()
        new_srt = refiner.refine_with_video_context(youtube_id)
        
        if new_srt:
            if video.transcription:
                video.transcription.refinado_srt = new_srt
                video.transcription.has_gemini = True
            db.commit()
            logger.info(f"Refinamiento completado ✅ para {youtube_id}")
            return {"status": "success", "refined_raw": new_srt}
        else:
            return {"status": "error", "message": "No se pudo generar el refinamiento"}
    except Exception as e:
        logger.error(f"Error en refinamiento avanzado: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

@app.post("/api/download-vtt/{youtube_id}")
def download_single_vtt(youtube_id: str):
    """Descarga el VTT de un solo vídeo usando yt-dlp y lo guarda en la BD (síncrono)."""
    import subprocess, sys, tempfile

    db = SessionLocal()
    try:
        video = db.query(Video).filter_by(youtube_id=youtube_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        video_id = video.id
    finally:
        db.close()

    url = f"https://www.youtube.com/watch?v={youtube_id}"
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, f"{youtube_id}.%(ext)s")
    expected_file = os.path.join(tmp_dir, f"{youtube_id}.es.vtt")

    cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

    # Intentar primero SIN cookies (auto-subs no requieren auth normalmente)
    # Si falla, reintentar CON cookies
    attempts = [
        {
            "label": "sin cookies",
            "cmd": [
                sys.executable, "-m", "yt_dlp",
                "--write-auto-subs",
                "--skip-download",
                "--sub-langs", "es",
                "--sub-format", "vtt",
                "-o", output_template,
                "--no-check-certificates",
                url
            ]
        },
        {
            "label": "con cookies",
            "cmd": [
                sys.executable, "-m", "yt_dlp",
                "--cookies", cookies_path,
                "--write-auto-subs",
                "--skip-download",
                "--sub-langs", "es",
                "--sub-format", "vtt",
                "-o", output_template,
                url
            ]
        }
    ]

    try:
        for attempt in attempts:
            logger.info(f"Descargando VTT individual para {youtube_id} ({attempt['label']})...")
            process = subprocess.run(attempt["cmd"], capture_output=True, text=True, timeout=120)

            if os.path.exists(expected_file):
                with open(expected_file, 'r', encoding='utf-8') as f:
                    vtt_content = f.read()
                os.remove(expected_file)

                # Guardar en BD
                db2 = SessionLocal()
                try:
                    existing = db2.query(Transcription).filter_by(video_id=video_id).first()
                    if existing:
                        existing.vtt = vtt_content
                    else:
                        new_t = Transcription(video_id=video_id, vtt=vtt_content, language='es')
                        db2.add(new_t)
                    db2.commit()
                    logger.info(f"✅ VTT guardado en BD para {youtube_id} ({len(vtt_content)} chars) [{attempt['label']}]")
                finally:
                    db2.close()

                return {"status": "success", "message": f"✅ VTT descargado y guardado ({len(vtt_content)} caracteres)"}
            else:
                stderr_msg = process.stderr[:500] if process.stderr else "Sin detalles"
                logger.warning(f"Intento {attempt['label']} falló para {youtube_id}: {stderr_msg}")

        # Si ningún intento funcionó
        return {"status": "error", "message": f"❌ No se encontraron subtítulos en español para este vídeo"}

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout descargando VTT para {youtube_id}")
        return {"status": "error", "message": "❌ Timeout: YouTube tardó demasiado en responder"}
    except Exception as e:
        logger.error(f"Error descargando VTT para {youtube_id}: {e}")
        return {"status": "error", "message": f"❌ Error: {str(e)}"}

@app.post("/api/process-pending")
def process_pending_api(background_tasks: BackgroundTasks):
    """Descarga los VTTs que faltan usando yt-dlp."""
    def do_process():
        try:
            import subprocess
            logger.info("Iniciando descarga de VTTs pendientes...")
            with open("dashboard_process.log", "w", encoding="utf-8") as f:
                subprocess.run(["python3", "-u", "scripts/database/download_missing_vtt.py"], stdout=f, stderr=subprocess.STDOUT)
            logger.info("Descarga de VTTs completada ✅")
        except Exception as e:
            logger.error(f"Error descargando VTTs: {e}")

    background_tasks.add_task(do_process)
    return {"status": "started", "message": "Descargando VTTs pendientes en segundo plano..."}

@app.get("/api/process-log")
def get_process_log():
    """Devuelve las últimas líneas del log de procesamiento en tiempo real."""
    import os
    if not os.path.exists("dashboard_process.log"):
        return {"log": "Proceso inactivo o esperando inicio..."}
    try:
        with open("dashboard_process.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            return {"log": "".join(lines[-30:])}
    except Exception as e:
        return {"log": f"Error leyendo log: {e}"}

@app.get("/")
def read_root():
    return FileResponse("manager_dashboard.html")

@app.get("/manager_dashboard.html")
def read_dashboard_explicit():
    return FileResponse("manager_dashboard_v2.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
