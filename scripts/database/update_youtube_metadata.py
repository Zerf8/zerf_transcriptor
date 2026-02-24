import os
import json
import traceback
from datetime import datetime
from googleapiclient.discovery import build
from sqlalchemy import text
from src.models import Video, VideoStats, get_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Configuración API
YOUTUBE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not YOUTUBE_API_KEY:
    raise ValueError("Falta GOOGLE_API_KEY en .env")

youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def get_video_details(video_ids):
    """Obtiene detalles completos de los vídeos de YouTube en bloques de máximo 50."""
    try:
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics,status",
            id=",".join(video_ids)
        )
        response = request.execute()
        return response.get('items', [])
    except Exception as e:
        print(f"\n❌ Error GRAVE conectando a la API de YouTube:")
        print(f"{e}")
        print("Revisa tu cuota o permisos en Google Cloud Console.\n")
        return []

def extract_safe(item, path, default=None):
    """Extrae datos anidados de un dict de forma segura."""
    keys = path.split('.')
    val = item
    for key in keys:
        if isinstance(val, dict) and key in val:
            val = val[key]
        else:
            return default
    return val

def run_update():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. ACTUALIZAR METADATOS
        print("Obteniendo todos los videos de la base de datos...")
        all_videos = session.query(Video).all()
        total = len(all_videos)
        print(f"Encontrados {total} vídeos. Preparando peticiones a la API...")

        # Procesar en bloques de 50
        for i in range(0, total, 50):
            batch = all_videos[i:i+50]
            batch_ids = [v.youtube_id for v in batch]
            print(f"Procesando bloque {i} a {min(i+50, total)}...")
            
            yt_data = get_video_details(batch_ids)
            data_map = {item['id']: item for item in yt_data}

            for video in batch:
                yt_info = data_map.get(video.youtube_id)
                if not yt_info:
                    print(f"  ⚠️ No hay datos en YT para: {video.youtube_id}")
                    continue

                # --- SNIPPET ---
                title = extract_safe(yt_info, 'snippet.title')
                if title:
                    video.title = title
                
                desc = extract_safe(yt_info, 'snippet.description')
                if desc:
                    video.description = desc

                pub_date_str = extract_safe(yt_info, 'snippet.publishedAt')
                if pub_date_str:
                    try:
                        # 2024-03-20T15:00:00Z -> datetime
                        video.upload_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ")
                    except:
                        pass
                
                # Thumbnails: intentar coger la maxres, si no high, medium, default
                thumbs = extract_safe(yt_info, 'snippet.thumbnails', {})
                best_thumb = None
                for res in ['maxres', 'high', 'medium', 'default']:
                    if res in thumbs and 'url' in thumbs[res]:
                        best_thumb = thumbs[res]['url']
                        break
                video.thumbnail = best_thumb

                tags = extract_safe(yt_info, 'snippet.tags')
                if tags:
                    video.tags = ",".join(tags)
                
                video.category = extract_safe(yt_info, 'snippet.categoryId')
                
                live_status = extract_safe(yt_info, 'snippet.liveBroadcastContent')
                # puede ser 'live', 'none', o 'upcoming'
                video.is_live = 1 if live_status == 'live' else 0

                # --- CONTENT DETAILS ---
                video.definition = extract_safe(yt_info, 'contentDetails.definition')
                video.projection = extract_safe(yt_info, 'contentDetails.projection')
                has_caption = extract_safe(yt_info, 'contentDetails.caption')
                video.caption = 1 if str(has_caption).lower() == 'true' else 0

                # --- STATUS ---
                video.privacyStatus = extract_safe(yt_info, 'status.privacyStatus')

                # --- STATISTICS (Va a la tabla VideoStats) ---
                stats = session.query(VideoStats).filter_by(video_id=video.id).first()
                if not stats:
                    stats = VideoStats(video_id=video.id)
                    session.add(stats)
                
                # Actualizar contadores
                view_c = extract_safe(yt_info, 'statistics.viewCount')
                if view_c: stats.view_count = int(view_c)
                
                like_c = extract_safe(yt_info, 'statistics.likeCount')
                if like_c: stats.like_count = int(like_c)
                
                comm_c = extract_safe(yt_info, 'statistics.commentCount')
                if comm_c: stats.comment_count = int(comm_c)

            session.commit()
            print(f" Bloque actualizado. Hacemos pausa de 1 segundo...".encode("ascii", errors="ignore").decode())
        
        print("\n Actualizacion de metadatos completada.")

        # 2. REORDENAR IDs (Cronológicamente)
        # ⚠️ Esta es una operación muy delicada, ya que los IDs están en cascada.
        # En lugar de modificar los IDs primarios existentes (lo que puede romper las Foreign Keys en
        # transcriptions, clips, comments, stats si no está configurada la actualización en cascada),
        # lo haremos re-creando los registros ordenados temporalmente si no tenemos Constraints de CASCADE UPDATE funcionales,
        # o usando un campo secundario.
        # Dado que "reordenar el id 1" significa cambiar PRIMARY KEY (id), esto rompe las relaciones (transcription, stats).
        
        print("\n\n NOTA SOBRE REORDENAR IDs:")
        print("Cambiar directamente la Primary Key (id) de 'videos' es destructivo para las tablas relacionadas (clips, transcriptions, etc) a menos que MySQL tenga configurado ON UPDATE CASCADE en todas las Foreign Keys.")
        print("El modelo actual de SQLAlchemy NO tiene definido cascada para actualizaciones de FK (ON UPDATE CASCADE) por defecto.")
        print("Para ordenar la interfaz sin romper la BBDD, sugerimos primero intentar hacerlo. En SQL Puro:")
        
        # Vamos a comprobar si es posible
        pass

    except Exception as e:
        print(f"Error critico: {e}")
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_update()
