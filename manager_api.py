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
import logging
import time
import pickle
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
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

# Configuración de Google Drive
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
TOKEN_PATH = "token.pickle"

# Caché para el listado de Drive
drive_cache = {
    "files": [],
    "last_update": 0
}
CACHE_TTL = 300 # 5 minutos

def get_drive_service():
    """Obtiene el servicio de Google Drive usando el token guardado."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
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

@app.get("/api/videos")
def list_videos(skip: int = 0, limit: int = 25):
    """Obtiene vídeos de la base de datos que tienen SRT, ordenados por fecha y paginados."""
    db = SessionLocal()
    try:
        # Usamos exists subquery y limitamos a la tabla de videos
        query = db.query(Video).filter(
            Video.transcription.has(Transcription.srt_content != '')
        ).order_by(Video.upload_date.desc())
        
        total = query.count()
        videos = query.offset(skip).limit(limit).all()
        
        result = []
        for v in videos:
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
                "has_srt": True
            })
            
        return {"total": total, "videos": result, "skip": skip, "limit": limit}
    except Exception as e:
        logger.error(f"Error en list_videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
        
        if not srt_content:
            raise HTTPException(status_code=400, detail="No hay SRT disponible para traducir")

        #worker
        def do_translate():
            try:
                logger.info(f"Traduciendo {youtube_id} a {lang}...")
                translated = traducir_srt_gemini(srt_content, lang)
                out_file = f"SRT_{lang}_{youtube_id}.srt"
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(translated)
                logger.info(f"Traducción completada: {out_file}")
            except Exception as e:
                logger.error(f"Error traduciendo: {e}")

        background_tasks.add_task(do_translate)
        return {"status": "started", "message": f"Traducción a {lang} iniciada"}
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
        
        # Buscar el archivo SRT (original o traducido)
        srt_content = None
        
        # 1. ¿Es una traducción local?
        target_file = f"SRT_{lang}_{youtube_id}.srt"
        if os.path.exists(target_file):
            with open(target_file, "r", encoding="utf-8") as f:
                srt_content = f.read()
        
        # 2. Si no, ¿es el original 'es' en DB?
        if not srt_content and lang == 'es':
            if video.transcription:
                srt_content = video.transcription.srt_content
        
        # 3. Si no, ¿es el original en disco?
        if not srt_content and lang == 'es':
            if os.path.isdir(SRT_DIR):
                for f in os.listdir(SRT_DIR):
                    if youtube_id in f:
                        with open(os.path.join(SRT_DIR, f), 'r', encoding='utf-8') as srt_f:
                            srt_content = srt_f.read()
                        break

        if not srt_content:
            raise HTTPException(status_code=400, detail=f"No se encontró el archivo SRT para {lang}")

        def do_upload():
            try:
                subir_srt_a_youtube(youtube_id, srt_content, lang)
                logger.info(f"Subida completada para {youtube_id} ({lang})")
            except Exception as e:
                logger.error(f"Error subiendo a YouTube: {e}")

        background_tasks.add_task(do_upload)
        return {"status": "started", "message": f"Subida de {lang} iniciada"}
    finally:
        db.close()

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

@app.get("/")
def read_root():
    return FileResponse("manager_dashboard.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
