import yt_dlp
import os
import traceback
import time
from datetime import datetime
from src.models import Video, VideoStats, Transcription, Clip, Comment, get_engine, Base
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Usar /videos para asegurar que extraemos TODOS los videos del canal
CHANNEL_URL = "https://www.youtube.com/@ZerfFCB/videos"
LOG_FILE = r"c:\proyectos\Zerf_Transcriptor\sync_debug.log"

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()}: {msg}\n")

def format_duration(seconds):
    if not seconds: return None
    try:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h:02}:{m:02}:{s:02}"
        return f"{m:02}:{s:02}"
    except:
        return None

def fetch_all_videos_fast():
    log(f"🔍 Extrayendo metadatos BÁSICOS (Modo Seguro) de YouTube: {CHANNEL_URL}...")
    # Modo 'flat' extrae mucho más rápido y evita bloqueos por rate-limit
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist', 
        'force_generic_extractor': False,
        'playlist_items': '1-2000', # Margen de seguridad
        'sleep_interval': 1, # Un poco de cortesía con YouTube
        'max_sleep_interval': 5,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        processed_info = ydl.extract_info(CHANNEL_URL, download=False)
        entries = processed_info.get('entries', [])
        
        videos = []
        for entry in entries:
            if not entry: continue
            
            # En modo flat, algunos campos pueden venir diferentes
            videos.append({
                'youtube_id': entry.get('id'),
                'title': entry.get('title'),
                'duration': entry.get('duration'),
                'upload_date': entry.get('upload_date'), # Puede venir como string YYYYMMDD
                'channel': entry.get('uploader') or 'ZerfFCB',
                'view_count': entry.get('view_count'),
                'url': entry.get('url')
            })
        
        # Ordenar por fecha (más antiguo primero)
        # Parsear fechas si vienen como string
        for v in videos:
            if isinstance(v['upload_date'], str):
                try:
                    v['upload_date'] = datetime.strptime(v['upload_date'], '%Y%m%d')
                except:
                    v['upload_date'] = None
                    
        videos.sort(key=lambda x: (x['upload_date'] if x['upload_date'] else datetime.max, x['youtube_id']))
        return videos

def sync():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
        
    try:
        engine = get_engine()
        Session = sessionmaker(bind=engine)
        
        # --- FASE 1: BACKUP ---
        log("📦 Haciendo backup de datos existentes (RAW)...")
        session = Session()
        transcription_map = {}
        for t in session.query(Transcription).all():
            video = session.query(Video).filter_by(id=t.video_id).first()
            if video:
                transcription_map[video.youtube_id] = {
                    'whisper_text': t.whisper_text,
                    'gemini_text': t.gemini_text,
                    'srt_content': t.srt_content,
                    'raw_json': t.raw_json,
                    'language': t.language
                }
            
        clips_map = {}
        for c in session.query(Clip).all():
            video = session.query(Video).filter_by(id=c.video_id).first()
            if video:
                if video.youtube_id not in clips_map:
                    clips_map[video.youtube_id] = []
                clips_map[video.youtube_id].append({
                    'start_time': c.start_time,
                    'end_time': c.end_time,
                    'start_seconds': c.start_seconds,
                    'end_seconds': c.end_seconds,
                    'text_preview': c.text_preview,
                    'score': c.score,
                    'reason': c.reason,
                    'tags': c.tags,
                    'source': c.source
                })
        session.close()
        
        # --- FASE 2: EXTRACCIÓN YOUTUBE (FAST) ---
        all_videos = fetch_all_videos_fast()
        log(f"🎬 Encontrados {len(all_videos)} videos en YouTube (Modo Rápido).")

        # --- FASE 3: LIMPIEZA E INSERCIÓN ---
        log("🚀 Iniciando inserción RÁPIDA a Hostinger...")
        session = Session()
        
        log("🧹 Reiniciando esquema de tablas...")
        with engine.connect() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            Base.metadata.drop_all(conn)
            Base.metadata.create_all(conn)
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()

        for idx, v_data in enumerate(all_videos, 1):
            # Solo datos básicos disponibles en flat
            video = Video(
                youtube_id=v_data['youtube_id'],
                title=v_data['title'],
                duration=v_data['duration'],
                duration_string=format_duration(v_data['duration']),
                upload_date=v_data['upload_date'],
                channel=v_data['channel'],
                status='migrated'
            )
            session.add(video)
            session.flush() 
            
            # Crear stats vacíos o básicos
            stats = VideoStats(
                video_id=video.id,
                view_count=v_data.get('view_count'),
                like_count=0,
                comment_count=0
            )
            session.add(stats)
            
            # Restaurar transcripciones
            if v_data['youtube_id'] in transcription_map:
                t_data = transcription_map[v_data['youtube_id']]
                transcription = Transcription(
                    video_id=video.id,
                    whisper_text=t_data['whisper_text'],
                    gemini_text=t_data['gemini_text'],
                    srt_content=t_data['srt_content'],
                    raw_json=t_data['raw_json'],
                    language=t_data['language']
                )
                session.add(transcription)
                
            # Restaurar clips
            if v_data['youtube_id'] in clips_map:
                for c_data in clips_map[v_data['youtube_id']]:
                    clip = Clip(
                        video_id=video.id,
                        start_time=c_data['start_time'],
                        end_time=c_data['end_time'],
                        start_seconds=c_data['start_seconds'],
                        end_seconds=c_data['end_seconds'],
                        text_preview=c_data['text_preview'],
                        score=c_data['score'],
                        reason=c_data['reason'],
                        tags=c_data['tags'],
                        source=c_data['source']
                    )
                    session.add(clip)
            
            if idx % 100 == 0:
                log(f"✅ Procesados {idx}/{len(all_videos)}...")
                session.commit()

        session.commit()
        log(f"✨ ¡Sincronización BÁSICA completada! ({len(all_videos)} videos). Los metadatos detallados se actualizarán progresivamente.")
        session.close()
        
    except Exception as e:
        err = traceback.format_exc()
        log(f"❌ ERROR:\n{err}")

if __name__ == "__main__":
    sync()
