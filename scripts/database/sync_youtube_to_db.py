import os
import yt_dlp
from datetime import datetime
from googleapiclient.discovery import build
from sqlalchemy.orm import sessionmaker
from src.models import Video, VideoStats, get_engine
from dotenv import load_dotenv
import json
import re

load_dotenv()

# Configuración
CHANNEL_URL = "https://www.youtube.com/@ZerfFCB/videos"
YOUTUBE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not YOUTUBE_API_KEY:
    raise ValueError("Falta GOOGLE_API_KEY en .env")

youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

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

def get_channel_videos_via_api(channel_handle):
    """Obtiene IDs de los últimos vídeos de un canal usando la API de YouTube."""
    try:
        # 1. Obtener ID del canal desde el handle
        # Nota: En un caso real podrías tener el Channel ID guardado. 
        # Pero podemos obtener los últimos vídeos de ZerfFCB si sabemos su ID.
        # ID de ZerfFCB (obtenido de metadatos anteriores): UCc_rWk6DMC5H-D_XyC-B_sw (ejemplo)
        # Vamos a buscar el canal primero
        request = youtube.search().list(
            q=channel_handle,
            type="channel",
            part="id"
        )
        response = request.execute()
        if not response.get('items'): return []
        channel_id = response['items'][0]['id']['channelId']

        # 2. Obtener vídeos recientes del canal
        request = youtube.search().list(
            channelId=channel_id,
            part="id,snippet",
            order="date",
            type="video",
            maxResults=10
        )
        response = request.execute()
        return [item['id']['videoId'] for item in response.get('items', [])]
    except Exception as e:
        print(f"❌ Error API YouTube (Search): {e}")
        return []

def get_full_metadata(video_ids):
    """Obtiene detalles completos de los vídeos usando la YouTube Data API."""
    try:
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics,status",
            id=",".join(video_ids)
        )
        response = request.execute()
        return response.get('items', [])
    except Exception as e:
        print(f"❌ Error API YouTube (Videos.list): {e}")
        return []

def parse_duration(duration_str):
    """Convierte ISO 8601 duration (PT1M30S) a segundos sin dependencias externas."""
    import re
    patterns = [
        r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',
    ]
    for pattern in patterns:
        match = re.match(pattern, duration_str)
        if match:
            h = int(match.group(1)) if match.group(1) else 0
            m = int(match.group(2)) if match.group(2) else 0
            s = int(match.group(3)) if match.group(3) else 0
            return h * 3600 + m * 60 + s
    return 0

def format_duration(seconds):
    if not seconds: return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02}:{m:02}:{s:02}"
    return f"{m:02}:{s:02}"

def sync_new_videos():
    print(f"🔍 Buscando videos recientes en YouTube (vía API)...")
    
    # 1. Obtener IDs recientes usando la API (más fiable que yt-dlp para metadatos)
    recent_ids = get_channel_videos_via_api("@ZerfFCB")

    if not recent_ids:
        # Fallback a yt-dlp si la búsqueda falla (aunque suele ser al revés)
        print("⚠️ Búsqueda API falló, intentando yt-dlp...")
        ydl_opts = {'quiet': True, 'extract_flat': True, 'playlist_end': 5}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(CHANNEL_URL, download=False)
                recent_ids = [entry['id'] for entry in info.get('entries', []) if entry.get('id')]
            except: pass

    if not recent_ids:
        print("No se encontraron vídeos.")
        return

    # 2. Conectar a DB y ver cuáles no tenemos
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    existing_ids = set()
    rows = session.query(Video.youtube_id).filter(Video.youtube_id.in_(recent_ids)).all()
    existing_ids = {r[0] for r in rows}
    
    new_ids = [yid for yid in recent_ids if yid not in existing_ids]
    
    if not new_ids:
        print("✅ La base de datos ya está al día.")
        session.close()
        return

    print(f"✨ Detectados {len(new_ids)} vídeos nuevos. Extrayendo metadatos completos...")

    # 3. Obtener metadatos ricos de los nuevos vídeos
    yt_items = get_full_metadata(new_ids)
    
    for item in yt_items:
        yid = item['id']
        snippet = item.get('snippet', {})
        content = item.get('contentDetails', {})
        statistics = item.get('statistics', {})
        
        # Parsear fecha
        pub_date_str = snippet.get('publishedAt')
        upload_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ") if pub_date_str else datetime.now()
        
        # Duración
        duration_iso = content.get('duration')
        duration_sec = parse_duration(duration_iso) if duration_iso else 0
        
        # Tags
        tags_list = snippet.get('tags', [])
        tags_str = ",".join(tags_list) if tags_list else None
        
        # Thumbnail
        thumbs = snippet.get('thumbnails', {})
        best_thumb = None
        for res in ['maxres', 'high', 'medium', 'default']:
            if res in thumbs:
                best_thumb = thumbs[res]['url']
                break

        video = Video(
            youtube_id=yid,
            title=snippet.get('title'),
            description=snippet.get('description'),
            duration=duration_sec,
            duration_string=format_duration(duration_sec),
            upload_date=upload_date,
            channel=snippet.get('channelTitle', 'ZerfFCB'),
            thumbnail=best_thumb,
            tags=tags_str,
            category=snippet.get('categoryId'),
            is_live=1 if snippet.get('liveBroadcastContent') == 'live' else 0,
            definition=content.get('definition'),
            projection=content.get('projection'),
            caption=1 if content.get('caption') == 'true' else 0,
            status='pending'
        )
        session.add(video)
        session.flush()

        # Stats iniciales
        stats = VideoStats(
            video_id=video.id,
            view_count=int(statistics.get('view_count', 0)),
            like_count=int(statistics.get('like_count', 0)),
            comment_count=int(statistics.get('comment_count', 0))
        )
        session.add(stats)
        print(f"  + Añadido a DB: {video.title}")

    try:
        session.commit()
        print(f"🚀 Sincronización finalizada con éxito.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error guardando en DB: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    sync_new_videos()
