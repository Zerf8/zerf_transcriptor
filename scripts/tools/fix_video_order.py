import yt_dlp
import os
import traceback
from datetime import datetime
from src.models import Video, VideoStats, Transcription, Clip, get_engine, Base
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

LISTA_MAESTRA = r"c:\proyectos\Zerf_Transcriptor\lista_maestra_videos.txt"
CHANNEL_URL = "https://www.youtube.com/@ZerfFCB/videos"

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

def get_videos_from_file():
    if not os.path.exists(LISTA_MAESTRA):
        return []
    
    videos = []
    with open(LISTA_MAESTRA, "r", encoding="utf-8") as f:
        for line in f:
            if "youtube.com" in line:
                try:
                    parts = line.strip().split(maxsplit=2)
                    url = parts[0]
                    if "v=" in url:
                        vid_id = url.split("v=")[1].split("&")[0]
                        videos.append(vid_id)
                    elif "youtu.be/" in url:
                        vid_id = url.split("youtu.be/")[1].split("?")[0]
                        videos.append(vid_id)
                except:
                    continue
    # La lista va del más nuevo al más viejo. Invertimos.
    return list(reversed(videos))

def fetch_all_videos_fast():
    print(f"🔍 Recuperando metadatos de YouTube (porque la DB se vació)...")
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist', 
        'force_generic_extractor': False,
        'playlist_items': '1-2000',
        'sleep_interval': 1,
        'max_sleep_interval': 3,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        processed_info = ydl.extract_info(CHANNEL_URL, download=False)
        entries = processed_info.get('entries', [])
        
        videos = []
        for entry in entries:
            if not entry: continue
            videos.append({
                'youtube_id': entry.get('id'),
                'title': entry.get('title'),
                'duration': entry.get('duration'),
                'url': entry.get('url'),
                'upload_date': entry.get('upload_date'),
                'channel': entry.get('uploader') or 'ZerfFCB',
                'view_count': entry.get('view_count')
            })
            
        # Parse dates
        for v in videos:
             if isinstance(v['upload_date'], str):
                try:
                    v['upload_date'] = datetime.strptime(v['upload_date'], '%Y%m%d')
                except:
                    v['upload_date'] = None
        return videos

def fix_order():
    try:
        engine = get_engine()
        Session = sessionmaker(bind=engine)
        
        # 1. Recuperar info OLD de Transcripciones/Clips (si queda algo, pero con TRUNCATE se perdió...)
        # Si la DB está vacía, no podemos recuperar transcripciones :(. 
        # Esperemos que el usuario tenga backup o que el truncate anterior fallara en cascade.
        # Pero asumamos que tenemos que repoblar los videos.
        
        # 2. Obtener videos frescos de YT
        all_videos_yt = fetch_all_videos_fast()
        print(f"🎬 Recuperados {len(all_videos_yt)} videos de YouTube.")
        
        video_map = {v['youtube_id']: v for v in all_videos_yt}

        # 3. Ordenar
        ordered_ids = get_videos_from_file()
        print(f"✅ Lista maestra tiene {len(ordered_ids)} videos.")
        
        final_list = []
        
        # A. Los de la lista (Prioridad Absoluta)
        for yid in ordered_ids:
            if yid in video_map:
                final_list.append(video_map[yid])
                del video_map[yid]
        
        # B. Los sobrantes
        remaining = list(video_map.values())
        print(f"⚠️ {len(remaining)} videos fuera de lista. Se añaden al final.")
        remaining.sort(key=lambda x: (x['upload_date'] if x['upload_date'] else datetime.max))
        final_list.extend(remaining)

        # 4. TRUNCATE y REINSERTAR
        print("🚀 Reorganizando tabla (TRUNCATE)...")
        session = Session()
        with engine.connect() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            conn.execute(text("TRUNCATE TABLE clips"))
            conn.execute(text("TRUNCATE TABLE transcriptions"))
            conn.execute(text("TRUNCATE TABLE video_stats")) # Nueva tabla
            conn.execute(text("TRUNCATE TABLE comments")) # Nueva tabla
            conn.execute(text("TRUNCATE TABLE videos"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()

        count = 0
        for v in final_list:
            new_video = Video(
                youtube_id=v['youtube_id'],
                title=v['title'],
                duration=v['duration'],
                duration_string=format_duration(v['duration']),
                upload_date=v['upload_date'],
                channel=v['channel'],
                status='migrated'
            )
            session.add(new_video)
            session.flush()
            
            # Stats vacíos initially
            session.add(VideoStats(
                video_id=new_video.id, 
                view_count=v.get('view_count'), 
                like_count=0, 
                comment_count=0
            ))

            count += 1
            if count % 100 == 0:
                print(f"✅ Insertados {count}/{len(final_list)}...")
                session.commit()
                
        session.commit()
        print(f"✨ ¡RESCATE COMPLETADO! {count} videos insertados en orden correcto.")
        session.close()

    except Exception as e:
        print("❌ Error fatal:")
        traceback.print_exc()

if __name__ == "__main__":
    fix_order()
