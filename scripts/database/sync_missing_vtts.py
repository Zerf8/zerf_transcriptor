"""
Este script busca videos en la base de datos que sí tienen registros de transcripción 
pero donde el campo VTT está vacío o nulo. Luego intenta descargar esos subtítulos 
directamente de YouTube usando yt-dlp (con soporte experimental via Deno) 
y guarda el contenido en la base de datos si tiene éxito.
"""
import os
import sys
import glob

# Configurar path para imports de src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.models import get_engine, Video, Transcription
from sqlalchemy.orm import sessionmaker
import yt_dlp

def get_missing_vtt_videos(session):
    # Buscar vídeos que tienen transcripción pero su campo vtt está nulo o vacío
    videos = session.query(Video).join(Transcription).filter(
        (Transcription.vtt == None) | (Transcription.vtt == '')
    ).all()
    return videos

def download_vtt(youtube_id, output_dir='videos'):
    os.makedirs(output_dir, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    
    # Añadir soporte Deno para JS challenges de YouTube y evitar bloqueos
    deno_path = os.path.expanduser('~/.deno/bin/deno')
    ydl_opts = {
        'skip_download': True, # No queremos video/audio, solo subtítulos
        'writesubtitles': True,
        'writeautomaticsub': True, # Coger también los auto-generados si no hay manuales
        'subtitleslangs': ['es', 'en'],
        'outtmpl': os.path.join(output_dir, f"{youtube_id}.%(ext)s"),
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'remote_components': 'ejs:github',
        'username': 'oauth2',
        'password': '',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Prioridad a subtítulos en español, luego inglés, o el primero que encuentre de auto-generados
        posibles_rutas = [
            os.path.join(output_dir, f"{youtube_id}.es.vtt"),
            os.path.join(output_dir, f"{youtube_id}.en.vtt")
        ]
        
        # Buscar cualquiera que haya dejado la descarga (ej. .es.vtt)
        vtt_encontrados = glob.glob(os.path.join(output_dir, f"{youtube_id}.*.vtt"))
        
        for ruta in posibles_rutas + vtt_encontrados:
            if os.path.exists(ruta):
                return ruta
        return None
    except Exception as e:
        print(f"  [!] Error descargando: {e}")
        return None

def main():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("🔍 Buscando vídeos sin VTT en la base de datos...")
        videos = get_missing_vtt_videos(session)
        print(f"📊 Encontrados: {len(videos)} vídeos.")
        
        # Limitar opcionalmente para evitar bloqueos masivos
        # videos = videos[:100]
        
        procesados = 0
        con_exito = 0
        
        for index, video in enumerate(videos, 1):
            print(f"[{index}/{len(videos)}] Intentando: {video.youtube_id} - {video.title[:40]}...")
            
            vtt_path = download_vtt(video.youtube_id)
            
            if vtt_path:
                try:
                    with open(vtt_path, 'r', encoding='utf-8') as f:
                        vtt_content = f.read()
                    
                    transcription = session.query(Transcription).filter_by(video_id=video.id).first()
                    if transcription:
                        transcription.vtt = vtt_content
                        session.commit()
                        con_exito += 1
                        print(f"  ✓ VTT guardado en DB!")
                    
                    # Limpiar archivo temporal
                    os.remove(vtt_path)
                except Exception as e:
                    print(f"  [!] Error procesando archivo: {e}")
            else:
                print(f"  ✗ No hay subtítulos disponibles en YouTube.")
            
            procesados += 1
            
            # Limpiar otros subtitulos que pudiesen quedar del mismo id (.en, auto, etc)
            for file in glob.glob(os.path.join('videos', f"{video.youtube_id}.*.vtt")):
                try: os.remove(file)
                except: pass
                
        print(f"\n🎉 Resumen: {procesados} procesados. {con_exito} VTT recuperados y guardados con éxito.")
                
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
