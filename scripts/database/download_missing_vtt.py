import os
import pymysql
import logging
import subprocess
import tempfile
import time
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DownloadMissingVTT")

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = int(os.getenv("DB_PORT", 3306))

DIR_VTT = os.path.join("data", "subtitles", "vtt")
if not os.path.exists(DIR_VTT):
    os.makedirs(DIR_VTT)

def run_ytdlp_download(youtube_id):
    """
    Descarga el auto-subs en español desde youtube usando yt-dlp 
    y lo guarda en la carpeta local VTT. Devuelve el contenido del archivo si éxito, si no None.
    """
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    temp_dir = tempfile.gettempdir()
    
    # El patron esperado de yt-dlp: youtube_id.es.vtt
    output_template = os.path.join(temp_dir, f"{youtube_id}.%(ext)s")
    expected_file = os.path.join(temp_dir, f"{youtube_id}.es.vtt")
    
    cookies_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cookies.txt")
    
    command = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".venv", "Scripts", "python"), 
        "-m", "yt_dlp",
        "--cookies", cookies_path,
        "--js-runtimes", "node", # Habilitamos Node.js para pasar el reto Anti-BOT
        "--remote-components", "ejs:github", # Solver EJS de GitHub
        "--impersonate", "chrome", # Imita huella de Chrome (requiere curl_cffi)
        "--write-auto-subs",
        "--skip-download", # No descargamos el video, solo subs
        "--sub-langs", "es",
        "--sub-format", "vtt",
        "-o", output_template,
        url
    ]
    
    try:
        # Ejecutamos yt-dlp
        process = subprocess.run(command, capture_output=True, text=True)
        
        if process.returncode != 0:
            logger.error(f"Error youtube-dl para {youtube_id}: {process.stderr}")
            return None
            
        if os.path.exists(expected_file):
            with open(expected_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Limpiamos copiándolo a nuestra carpeta local definitiva
            local_save = os.path.join(DIR_VTT, f"{youtube_id}.es.vtt")
            with open(local_save, 'w', encoding='utf-8') as f:
                f.write(content)
                
            # Borrar temporal    
            os.remove(expected_file)    
            return content
        else:
            logger.warning(f"yt-dlp NO generó archivo de subtítulo '.es.vtt' para {youtube_id}")
            return None
            
    except Exception as e:
        logger.error(f"Excepcion corriendo yt-dlp para {youtube_id}: {e}")
        return None

def download_and_sync_missing_vtts():
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # 1. Obtenemos los vídeos huérfanos de VTT
            query_missing = """
                SELECT v.id, v.youtube_id, v.title 
                FROM videos v 
                LEFT JOIN transcriptions t ON v.id = t.video_id 
                WHERE t.id IS NULL OR t.vtt IS NULL OR TRIM(t.vtt) = ''
            """
            cursor.execute(query_missing)
            missing_videos = cursor.fetchall()
            
            if not missing_videos:
                logger.info("¡Enhorabuena! No detecto ningún video faltante de VTT en BD.")
                return
                
            logger.info(f"Se dispondrá a descargar subs para {len(missing_videos)} vídeos pendientes...")
            
            # 2. Bucle de descarga y subida individual
            success_count = 0
            
            for idx, vid_info in enumerate(missing_videos):
                num_id = vid_info['id']
                yt_id = vid_info['youtube_id']
                title = vid_info['title']
                
                logger.info(f"[{idx+1}/{len(missing_videos)}] Descargando {yt_id} - '{title[:30]}...'")
                
                vtt_content = run_ytdlp_download(yt_id)
                
                if vtt_content:
                    # Inserción / Update en MySQL
                    insert_query = """
                        INSERT INTO transcriptions 
                        (video_id, vtt, language) 
                        VALUES (%s, %s, 'es')
                        ON DUPLICATE KEY UPDATE
                        vtt = VALUES(vtt)
                    """
                    cursor.execute(insert_query, (num_id, vtt_content))
                    connection.commit()
                    success_count += 1
                    logger.info(f" -> Guardado exitoso en base de datos para {yt_id}")
                else:
                    logger.info(f" -> Ignorado: Sin subs en español disponibles para {yt_id}.")
                
                # Sleep de 3 segundos para evitar ban por dlp requests rapido
                time.sleep(3)
                
            logger.info("="*50)
            logger.info(f"PROCESO FINALIZADO. {success_count} VTTs nuevos sincronizados de {len(missing_videos)} propuestos.")
            logger.info("="*50)
            
    except Exception as e:
        logger.error(f"Error de base de datos durante subida: {e}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

if __name__ == "__main__":
    download_and_sync_missing_vtts()
