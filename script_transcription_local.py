# -*- coding: utf-8 -*-
"""
Script de Transcripción Local (Zerfpino Edition)
Adaptado para: AMD Ryzen 9 3900X + NVIDIA GTX 1660 SUPER

Este script replica la lógica "Winner" del notebook de Colab pero optimizado para ejecución local.
"""

import os
import sys
import subprocess
import json
import time
import logging
import yt_dlp
import re
import unicodedata
import gc
import torch
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from src.models import Video, Transcription, get_engine
from src.transcriber import Transcriber
from src.youtube_downloader import YouTubeDownloader
# from src.youtube_oauth_fixed import get_token # Desactivado en favor de bgutil automatizado

# ==========================================
# CONFIGURACIÓN LOCAL
# ==========================================

# Rutas Base (Usamos rutas relativas al script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDER_AUDIO = os.path.join(BASE_DIR, "output", "Transcripts_Video", "AUDIO_MP3")
FALLBACK_DIR = os.path.join(BASE_DIR, "output", "fallback_transcriptions")
LOG_FILE = os.path.join(BASE_DIR, "transcription_log.txt")
DEBUG_MODE = True
CONSECUTIVE_ERROR_LIMIT = 3

# Configurar logging a fichero y consola
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# === BYPASS DE BLOQUEO (YouTube poToken Automatizado) ===
# El script ahora usa 'bgutil' que corre en el puerto 4416.
# Asegúrate de que el servidor Node.js esté activo.
# ==========================================

# Configuración de Transcripción
MODEL_SIZE = "large-v2"
NUM_VIDEOS_LIMIT = 1  # 0 para todos

# Contexto para el modelo
INITIAL_PROMPT = "Transcripción de análisis del FC Barcelona. Jugadores: Lamine Yamal, Lewandowski, Cubarsí, Fermín, Gavi, Pedri, Araújo, Koundé, Raphinha, Ter Stegen, Pau Víctor, Dani Olmo, Flick."

# ==========================================
# MOTOR DE DESCARGA (Lógica Robusta de main.py)
# ==========================================

class YouTubeDownloader:
    def __init__(self, output_dir: str = 'videos'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.api_key = os.getenv("GOOGLE_API_KEY")
    
    def extract_metadata(self, url: str) -> dict:
        video_id = url.split("v=")[-1] if "v=" in url else url.split("/")[-1]
        if "?" in video_id: video_id = video_id.split("?")[0]
        
        print(f"   📡 Obteniendo metadatos vía API para: {video_id}")
        
        try:
            from googleapiclient.discovery import build
            service = build('youtube', 'v3', developerKey=self.api_key)
            
            request = service.videos().list(part="snippet,contentDetails", id=video_id)
            response = request.execute()
            
            if not response.get('items'):
                return {'title': 'Sin título', 'duration': 0, 'upload_date': datetime.now(), 'video_id': video_id, 'channel': 'ZerfFCB'}
                
            item = response['items'][0]
            snippet = item['snippet']
            content = item['contentDetails']
            
            # Parsear duración ISO 8601 a segundos
            duration_iso = content.get('duration', 'PT0S')
            import re
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_iso)
            h = int(match.group(1)) if match and match.group(1) else 0
            m = int(match.group(2)) if match and match.group(2) else 0
            s = int(match.group(3)) if match and match.group(3) else 0
            duration_sec = h * 3600 + m * 60 + s
            
            pub_date_str = snippet.get('publishedAt')
            # 2024-11-20T17:00:00Z
            try:
                upload_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ")
            except:
                upload_date = datetime.now()
            
            return {
                'title': snippet.get('title', 'Sin título'),
                'duration': duration_sec,
                'upload_date': upload_date,
                'video_id': video_id,
                'channel': snippet.get('channelTitle', 'ZerfFCB')
            }
        except Exception as e:
            print(f"   ⚠️ Error API YouTube: {e}. Usando metadatos genéricos.")
            return {'title': 'Video YouTube', 'duration': 0, 'upload_date': datetime.now(), 'video_id': video_id, 'channel': 'Unknown'}

    def sanitize_filename(self, title: str) -> str:
        # Normalizar y limpiar para sistema de archivos
        import unicodedata
        title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
        clean = re.sub(r'[^\w\s-]', '', title)
        return clean[:80].strip()

    def download_video(self, url: str):
        metadata = self.extract_metadata(url)
        if not metadata: return None
        
        video_id = metadata['video_id']
        # El nombre final que usa este script local para MP3
        # Para ser compatibles con la lógica de main.py pero mantener el formato local:
        title_clean = self.sanitize_filename(metadata['title'])
        fecha_str = metadata['upload_date'].strftime('%Y%m%d')
        final_filename = f"{fecha_str}_{title_clean}_{video_id}"
        audio_path_final = os.path.join(self.output_dir, f"{final_filename}.mp3")
        vtt_path_final = os.path.join(self.output_dir, f"{final_filename}.es.vtt")

        if os.path.exists(audio_path_final):
            print(f"   ✅ Audio local encontrado: {audio_path_final}")
            metadata['youtube_vtt_path'] = vtt_path_final if os.path.exists(vtt_path_final) else None
            return (audio_path_final, metadata)

        # Configurar extractor args para usar el servidor bgutil local
        # También forzamos el path de deno para resolver el n-challenge
        deno_bin = "/home/ubuntu/.deno/bin/deno"
        
        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--cookies', 'cookies.txt',
            '--extractor-args', "youtube:player_client=mweb,android;pot_provider=bgutil",
            '--remote-components', 'ejs:github',
            '--js-runtimes', f'deno:{deno_bin}',
            '-f', 'ba/best',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '192K',
            '--write-auto-sub',
            '--sub-lang', 'es',
            '--convert-subs', 'vtt',
            '-o', os.path.join(self.output_dir, f"{final_filename}.%(ext)s"),
            url
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            
            if os.path.exists(audio_path_final):
                metadata['youtube_vtt_path'] = vtt_path_final if os.path.exists(vtt_path_final) else None
                return (audio_path_final, metadata)
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Error en yt-dlp: {e.stderr.decode() if e.stderr else str(e)}")
            
        return None

# Funciones write_srt y extraer_id_url eliminadas por ser dependientes de modo local

# ==========================================
# PROCESO PRINCIPAL
# ==========================================

def main():
    script_start = time.time()
    log.info("🚀 Iniciando Transcriptor Zerf (Servidor Ubuntu)")
    
    # 1. Verificar GPU
    if torch.cuda.is_available():
        log.info(f"✅ GPU Detectada: {torch.cuda.get_device_name(0)}")
        device = "cuda"
    else:
        log.info("⚠️ PRECAUCIÓN: GPU no detectada. Se usará CPU (será lento).")
        device = "cpu"

    # setup_directories()
    os.makedirs(FOLDER_AUDIO, exist_ok=True)
    os.makedirs(FALLBACK_DIR, exist_ok=True)
    log.info(f"📁 Directorio de audio verificado: {FOLDER_AUDIO}")
    log.info(f"📁 Directorio fallback: {FALLBACK_DIR}")

    # 3. Leer videos de la base de datos
    log.info("Conectando a la base de datos...")
    engine = get_engine()
    # Añadir timeouts para evitar conexiones colgadas
    engine.pool._recycle = 300
    Session = sessionmaker(bind=engine)

    # Test de conectividad BD
    log.info("Verificando conexión a la base de datos...")
    try:
        test_session = Session()
        test_session.execute("SELECT 1")
        test_session.close()
        log.info("✅ Conexión a BD verificada.")
    except Exception as e:
        log.error(f"❌ No se puede conectar a la BD: {e}")
        log.error("Las transcripciones se guardarán en archivos locales de fallback.")

    # Obtener lista de IDs pendientes en una sesión corta
    session = Session()
    try:
        videos_ids = [v.id for v in session.query(Video.id).outerjoin(Transcription).filter(
            (Transcription.id == None) | (Transcription.whisper_srt == None) | (Transcription.whisper_srt == '')
        ).order_by(Video.upload_date.desc()).all()]
    finally:
        session.close()

    log.info(f"📋 Encontrados {len(videos_ids)} videos sin transcripción en la BD.")

    try:
        # Inicializar herramientas
        downloader = YouTubeDownloader(FOLDER_AUDIO)
        transcriber = Transcriber(model_name="large-v2")

        videos_procesados_count = 0
        errores_consecutivos = 0
        procesado_exito = False
        
        for i, video_id_db in enumerate(videos_ids, 1):
            # Chequeo de seguridad del límite
            if NUM_VIDEOS_LIMIT > 0 and videos_procesados_count >= NUM_VIDEOS_LIMIT:
                print(f"🛑 Se ha alcanzado el límite de {NUM_VIDEOS_LIMIT} videos procesados.")
                break

            # Crear una sesión fresca para leer metadatos del vídeo
            session = Session()
            try:
                video = session.get(Video, video_id_db)
                if not video:
                    log.warning(f"   ⚠️ Video ID {video_id_db} no encontrado en BD. Saltando.")
                    session.close()
                    continue

                url = f"https://www.youtube.com/watch?v={video.youtube_id}"
                title_hint = video.title
                desc_hint = video.description or ""
                video_db_id = video.id  # Guardar ID para uso posterior
                
                # Prompt enriquecido
                current_prompt = f"{title_hint}. {desc_hint[:200]}. {INITIAL_PROMPT}"
                
                log.info(f"\n🎬 Procesando [{i}/{len(videos_ids)}]: {url} (DB ID: {video_db_id})")
            finally:
                session.close()  # Cerrar ANTES de la descarga/transcripción larga

                # 1. Descargar video y extraer metadata (usando el downloader del proyecto)
            t_download = time.time()
            try:
                download_result = downloader.download_video(url)
                if not download_result:
                    raise Exception("Error en descarga o extracción de metadata")
                
                audio_path, info = download_result
                nombre_final = info.get('title', 'video')
                vtt_local_path = info.get('youtube_vtt_path')
                
                elapsed_dl = time.time() - t_download
                log.info(f"   🏷️ Título: {nombre_final}")
                log.info(f"   ⬇️ Descarga completada en {elapsed_dl:.1f}s")
                if vtt_local_path:
                    log.info(f"   📄 Subtítulos VTT descargados: {vtt_local_path}")
            except Exception as e:
                elapsed_dl = time.time() - t_download
                log.error(f"   ⚠️ Fallo en descarga ({elapsed_dl:.1f}s): {e}")
                errores_consecutivos += 1
                if errores_consecutivos >= 3:
                    log.error("🛑 Demasiados errores consecutivos (3). Abortando el script...")
                    break
                continue

            # Transcribir (LARGA OPERACIÓN — sin conexión DB abierta)
            t_transcribe = time.time()
            try:
                log.info("   🎤 Transcribiendo (Whisper Large)... esto tomará unos minutos...")
                transcriber.initial_prompt = current_prompt
                result = transcriber.transcribe_audio(audio_path)
                
                if not result:
                    raise Exception("Error en transcripción")

                srt_final_content = transcriber.generate_srt_string(result['segments'])
                texto_completo = result['text'].strip()
                elapsed_tr = time.time() - t_transcribe
                log.info(f"   ✍️ Transcripción completada en {elapsed_tr:.1f}s ({elapsed_tr/60:.1f} min)")
            except Exception as e:
                elapsed_tr = time.time() - t_transcribe
                log.error(f"   ❌ Error en transcripción ({elapsed_tr:.1f}s): {e}")
                errores_consecutivos += 1
                if errores_consecutivos >= 3:
                    log.error("🛑 Demasiados errores consecutivos (3). Abortando el script...")
                    break
                continue

            # Ahora abrir una sesión fresca para el guardado en BD
            session = Session()
            try:
                # Re-cargar el vídeo con la sesión fresca
                video = session.get(Video, video_db_id)

                # Aplicar alineación de VTT si el vídeo original tiene vtt disponible
                vtt_existente = None
                trans_existente = session.query(Transcription).filter_by(video_id=video_db_id).first()
                if trans_existente and trans_existente.vtt:
                    vtt_existente = trans_existente.vtt
                
                if not vtt_existente and vtt_local_path:
                    if os.path.exists(vtt_local_path):
                        with open(vtt_local_path, 'r', encoding='utf-8') as f:
                            vtt_existente = f.read()

                if vtt_existente:
                    log.info("   🔗 VTT original encontrado. Alineando tiempos de Whisper...")
                    
                    vtt_temp_path = "/tmp/temp_vtt.vtt"
                    with open(vtt_temp_path, 'w', encoding='utf-8') as f:
                        f.write(vtt_existente)
                        
                    temp_srt = "/tmp/temp_whisper.srt"
                    with open(temp_srt, 'w', encoding='utf-8') as f:
                        f.write(srt_final_content)
                        
                    transcriber.generate_srt_from_vtt(srt_final_content, vtt_temp_path, temp_srt)
                    
                    with open(temp_srt, 'r', encoding='utf-8') as f:
                        srt_final_content = f.read()
                        
                    os.remove(temp_srt)
                    os.remove(vtt_temp_path)
                else:
                    log.info("   ⚠️ No hay subtítulos VTT disponibles para alinear. Usando tiempos crudos de Whisper.")
                
                log.info(f"   💾 Transcripción en memoria preparada.")
                
                # ==== GUARDAR EN BASE DE DATOS ====
                trans = trans_existente or Transcription(video_id=video_db_id)
                if not trans_existente:
                    session.add(trans)
                
                trans.whisper_text = result.get('text', '').strip()
                trans.whisper_srt = srt_final_content
                trans.srt_content = srt_final_content
                trans.vtt = vtt_existente
                trans.raw_json = json.dumps(result, ensure_ascii=False)
                trans.language = result.get('language', 'es')
                trans.updated_at = datetime.utcnow()
                
                # Actualizar estado del video
                video.status = 'completed'
                video.updated_at = datetime.utcnow()
                
                session.commit()
                elapsed_total = time.time() - t_download
                log.info(f"   ✅ [DB] Transcripción guardada para ID {video_db_id} — Total: {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)")
                
                videos_procesados_count += 1
                procesado_exito = True
                errores_consecutivos = 0

            except Exception as save_e:
                session.rollback()
                log.error(f"   ❌ Error guardando en BD: {save_e}")
                import traceback
                traceback.print_exc()
                
                # === FALLBACK: Guardar en archivo local ===
                log.warning(f"   📦 Guardando transcripción en fichero local de respaldo...")
                try:
                    fallback_data = {
                        'video_db_id': video_db_id,
                        'youtube_id': url.split('v=')[-1],
                        'whisper_text': result.get('text', '').strip(),
                        'whisper_srt': srt_final_content,
                        'vtt': vtt_existente,
                        'language': result.get('language', 'es'),
                        'raw_segments': result.get('segments', []),
                        'timestamp': datetime.utcnow().isoformat(),
                    }
                    fallback_path = os.path.join(FALLBACK_DIR, f"video_{video_db_id}.json")
                    with open(fallback_path, 'w', encoding='utf-8') as f:
                        json.dump(fallback_data, f, ensure_ascii=False, indent=2)
                    
                    # También guardar el SRT como archivo de texto independiente
                    srt_path = os.path.join(FALLBACK_DIR, f"video_{video_db_id}.srt")
                    with open(srt_path, 'w', encoding='utf-8') as f:
                        f.write(srt_final_content)
                    
                    log.info(f"   ✅ Fallback guardado: {fallback_path}")
                    log.info(f"   ✅ SRT guardado: {srt_path}")
                    videos_procesados_count += 1
                    procesado_exito = True
                    errores_consecutivos = 0
                except Exception as fallback_e:
                    log.error(f"   ❌ También falló el fallback local: {fallback_e}")
                    errores_consecutivos += 1
            finally:
                session.close()

            # Limpieza GPU (siempre al final de cada iteración)
            gc.collect()
            torch.cuda.empty_cache()

    except Exception as db_e:
        log.error(f"❌ Error al consultar la base de datos: {db_e}")

    elapsed_script = time.time() - script_start
    log.info(f"\n⏱️ Tiempo total del script: {elapsed_script:.1f}s ({elapsed_script/60:.1f} min)")
    log.info(f"📊 Videos procesados: {videos_procesados_count}")
    if procesado_exito:
        log.info("🎉 ¡PROCESO COMPLETADO CON ÉXITO!")
    else:
        log.warning("⚠️ PROCESO TERMINADO. No se completó ninguna transcripción.")

if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()
    main()
