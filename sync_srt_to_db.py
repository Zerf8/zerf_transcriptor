import os
from datetime import datetime
from googleapiclient.discovery import build
from src.models import VideoStats
from dotenv import load_dotenv
import re

load_dotenv()

# Configuración API
YOUTUBE_API_KEY = os.getenv("GOOGLE_API_KEY")

def get_youtube_service():
    if not YOUTUBE_API_KEY:
        return None
    return build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

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

def parse_duration(duration_str):
    """Convierte ISO 8601 duration (PT1M30S) a segundos."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
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

def fetch_metadata(youtube_id):
    """Obtiene los metadatos de un vídeo específico vía YouTube API v3."""
    youtube = get_youtube_service()
    if not youtube:
        print("❌ Error: No YOUTUBE_API_KEY configurada.")
        return None
        
    try:
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics,status",
            id=youtube_id
        )
        response = request.execute()
        items = response.get('items', [])
        return items[0] if items else None
    except Exception as e:
        print(f"❌ Error API YouTube: {e}")
        return None

def enriquecer_video(session, video, yt_info):
    """Actualiza el objeto Video con la información de YouTube."""
    if not yt_info:
        return False

    # --- SNIPPET ---
    snippet = yt_info.get('snippet', {})
    video.title = snippet.get('title', video.title)
    video.description = snippet.get('description', video.description)
    
    pub_date_str = snippet.get('publishedAt')
    if pub_date_str:
        try:
            video.upload_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ")
        except: pass

    # Thumbnail
    thumbs = snippet.get('thumbnails', {})
    best_thumb = None
    for res in ['maxres', 'high', 'medium', 'default']:
        if res in thumbs and 'url' in thumbs[res]:
            best_thumb = thumbs[res]['url']
            break
    if best_thumb:
        video.thumbnail = best_thumb

    tags = snippet.get('tags', [])
    if tags:
        video.tags = ",".join(tags)
    
    video.category = snippet.get('categoryId', video.category)
    video.is_live = 1 if snippet.get('liveBroadcastContent') == 'live' else 0

    # --- CONTENT DETAILS ---
    content = yt_info.get('contentDetails', {})
    video.definition = content.get('definition', video.definition)
    video.projection = content.get('projection', video.projection)
    video.caption = 1 if str(content.get('caption')).lower() == 'true' else 0
    
    duration_iso = content.get('duration')
    if duration_iso:
        video.duration = parse_duration(duration_iso)
        video.duration_string = format_duration(video.duration)

    # --- STATUS ---
    status = yt_info.get('status', {})
    # Aquí podrías guardar privacyStatus si existiera la columna, lo omitimos por ahora

    # --- STATISTICS ---
    statistics = yt_info.get('statistics', {})
    stats = session.query(VideoStats).filter_by(video_id=video.id).first()
    if not stats:
        stats = VideoStats(video_id=video.id)
        session.add(stats)
    
    stats.view_count = int(statistics.get('viewCount', 0))
    stats.like_count = int(statistics.get('likeCount', 0))
    stats.comment_count = int(statistics.get('commentCount', 0))

    # --- TRACKING ---
    video.metadata_updated_at = datetime.utcnow()
    
    return True
