import os
import sys
from requests_html import HTMLSession
from src.models import get_session, Video
from datetime import datetime

def get_latest_videos(channel_url="https://www.youtube.com/@ZerfFCB/videos", limit=5):
    print(f"📡 Buscando videos recientes en {channel_url}...")
    session = HTMLSession()
    response = session.get(channel_url)
    response.html.render(sleep=3, keep_page=True, scrolldown=1)

    videos = []
    # Usando selectores genéricos para anchors con /watch?v=
    links = response.html.find('a#video-title-link')
    
    for link in links:
        url = list(link.absolute_links)[0]
        title = link.attrs.get('title', 'Sin título')
        video_id = url.split("v=")[-1]
        
        if video_id not in [v['video_id'] for v in videos]:
            videos.append({
                'video_id': video_id,
                'title': title,
                'url': url
            })
            if len(videos) >= limit:
                break
                
    return videos

def sync_metadata_to_db():
    print("⏳ Iniciando sincronización de metadatos (bypassing Whisper)...")
    videos = get_latest_videos(limit=5)
    
    if not videos:
        print("❌ No se encontraron videos. Revisa la red o los selectores YouTube.")
        return

    db = get_session()
    try:
        new_count = 0
        for v in videos:
            print(f"🔍 Revisando: {v['video_id']} - {v['title'][:40]}...")
            
            # Buscar si ya existe
            existing = db.query(Video).filter(Video.video_id == v['video_id']).first()
            if not existing:
                print(f"   ✨ ¡NUEVO VÍDEO DETECTADO! Insertando en BD...")
                new_video = Video(
                    video_id=v['video_id'],
                    title=v['title'],
                    channel="ZerfFCB",
                    upload_date=datetime.now(), # Aproximación si no tiramos de API
                    duration=0
                )
                db.add(new_video)
                new_count += 1
            else:
                print("   ✅ Ya existe en la base de datos.")
                
        db.commit()
        print(f"\n🎉 Sincronización completada. {new_count} videos nuevos añadidos.")
    except Exception as e:
        print(f"❌ Error DB: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_metadata_to_db()
