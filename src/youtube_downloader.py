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
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',  # M4A comprimido (10-20x más pequeño que WAV)
                'preferredquality': '128',  # 128kbps es suficiente para transcripción
            }],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # La ruta final después de la conversión a M4A
            audio_path = os.path.join(self.output_dir, f"{video_id}.m4a")
            
            if os.path.exists(audio_path):
                print(f"✓ Descargado: {metadata['title']}")
                print(f"  Duración: {metadata['duration']//60}:{metadata['duration']%60:02d}")
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
