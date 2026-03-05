"""
Descargador de videos de YouTube
Usa yt-dlp para descargar audio y extraer metadata
"""
import yt_dlp
import os
import re
from datetime import datetime
from typing import Dict, Optional


class YouTubeDownloader:
    def __init__(self, output_dir: str = 'videos'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def extract_metadata(self, url: str) -> Optional[Dict]:
        """Extraer metadata sin descargar el video"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Extraer fecha de publicación
                upload_date = info.get('upload_date', '')
                if upload_date:
                    # Formato: YYYYMMDD
                    fecha = datetime.strptime(upload_date, '%Y%m%d')
                else:
                    fecha = datetime.now()
                
                return {
                    'title': info.get('title', 'Sin título'),
                    'duration': info.get('duration', 0),
                    'upload_date': fecha,
                    'video_id': info.get('id', ''),
                    'channel': info.get('uploader', '')
                }
        except Exception as e:
            print(f"Error extrayendo metadata: {e}")
            return None
    
    def sanitize_filename(self, title: str) -> str:
        """Limpiar título para nombre de archivo"""
        # Eliminar caracteres especiales
        clean = re.sub(r'[<>:"/\\|?*]', '', title)
        # Limitar longitud
        clean = clean[:100]
        return clean.strip()
    
    def format_output_name(self, metadata: Dict) -> str:
        """Generar nombre de archivo: yyyymmdd [título]"""
        fecha_str = metadata['upload_date'].strftime('%Y%m%d')
        title_clean = self.sanitize_filename(metadata['title'])
        return f"{fecha_str} {title_clean}"
    
    def download_video(self, url: str) -> Optional[tuple]:
        """
        Descargar audio del video
        Retorna: (ruta_archivo, metadata)
        """
        print(f"📥 Descargando: {url}")
        
        # Extraer metadata primero
        metadata = self.extract_metadata(url)
        if not metadata:
            return None
        
        video_id = metadata['video_id']
        output_path = os.path.join(self.output_dir, f"{video_id}.%(ext)s")
        
        # Configuración para descargar solo audio comprimido (mucho más rápido)
        # Añadimos soporte para OAuth2 y JS runtimes (Deno) para saltar bot detection
        deno_path = os.path.expanduser('~/.deno/bin/deno')
        ydl_opts = {
            'format': 'ba/best', # Cambiamos a ba/best para más flexibilidad
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
            'remote_components': 'ejs:github',
            'js_runtimes': f'deno:{deno_path}' if os.path.exists(deno_path) else 'deno',
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['es', 'en'],
            'subtitlesformat': 'vtt',
            'keepvideo': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '128',
            }],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # La ruta final después de la conversión a M4A
            audio_path = os.path.join(self.output_dir, f"{video_id}.m4a")
            vtt_path = os.path.join(self.output_dir, f"{video_id}.es.vtt")
            
            # Renombrar o mantener VTT
            vtt_final_path = None
            if os.path.exists(vtt_path):
                vtt_final_path = vtt_path
            elif os.path.exists(os.path.join(self.output_dir, f"{video_id}.en.vtt")):
                vtt_final_path = os.path.join(self.output_dir, f"{video_id}.en.vtt")

            
            if os.path.exists(audio_path):
                print(f"✓ Descargado: {metadata['title']}")
                print(f"  Duración: {metadata['duration']//60}:{metadata['duration']%60:02d}")
                if vtt_final_path:
                    print(f"  Subtítulos VTT encontrados: {vtt_final_path}")
                    metadata['youtube_vtt_path'] = vtt_final_path
                return (audio_path, metadata)
            else:
                print(f"✗ Error: archivo no encontrado después de descarga")
                return None
                
        except Exception as e:
            print(f"✗ Error descargando: {e}")
            return None
    
    def cleanup(self, file_path: str):
        """Eliminar archivo temporal"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️  Archivo temporal eliminado: {file_path}")
        except Exception as e:
            print(f"⚠️  No se pudo eliminar {file_path}: {e}")
