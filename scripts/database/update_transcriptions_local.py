import os
import pymysql
import logging
from tqdm import tqdm
from dotenv import load_dotenv

# Configuración de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LocalMigration")

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = int(os.getenv("DB_PORT", 3306))

DIR_VTT = os.path.join("data", "subtitles", "vtt")
DIR_SRT = os.path.join("data", "subtitles", "SRT_YouTube")

def extract_video_id(filename):
    name_without_ext = os.path.splitext(filename)[0]
    if name_without_ext.endswith('.es'):
        name_without_ext = name_without_ext[:-3]
    
    import re
    # 1. Busca IDs entre corchetes [ABCDEFGHIJK]
    match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', name_without_ext)
    if match:
        return match.group(1)
        
    # 2. Si el nombre es exactamente el ID de 11 caracteres
    if len(name_without_ext) == 11:
        return name_without_ext
        
    # 3. Si termina en un guión bajo seguido del ID de 11 caracteres (ej. Titulo_del_Video_IDVIDEO1234)
    match = re.search(r'_([a-zA-Z0-9_-]{11})$', name_without_ext)
    if match:
        return match.group(1)
        
    # 4. Fallback: asume que los últimos 11 caracteres son el ID
    if len(name_without_ext) > 11:
        return name_without_ext[-11:]
        
    return name_without_ext

def process_and_migrate_local(dry_run=False):
    transcriptions_data = {}

    if not os.path.exists(DIR_VTT):
        logger.warning(f"La carpeta {DIR_VTT} no existe.")
        vtt_files = []
    else:
        vtt_files = [f for f in os.listdir(DIR_VTT) if f.endswith('.vtt')]
        
    if not os.path.exists(DIR_SRT):
        logger.warning(f"La carpeta {DIR_SRT} no existe.")
        srt_files = []
    else:
        srt_files = [f for f in os.listdir(DIR_SRT) if f.endswith('.srt')]

    logger.info(f"Procesando {len(vtt_files)} archivos VTT...")
    for filename in tqdm(vtt_files, desc="Leyendo VTTs Local", unit="file"):
        filepath = os.path.join(DIR_VTT, filename)
        video_id = extract_video_id(filename)
        if video_id not in transcriptions_data:
            transcriptions_data[video_id] = {'vtt': None, 'whisper_srt': None}
        with open(filepath, 'r', encoding='utf-8') as f:
            transcriptions_data[video_id]['vtt'] = f.read()

    logger.info(f"Procesando {len(srt_files)} archivos SRT...")
    for filename in tqdm(srt_files, desc="Leyendo SRTs Local", unit="file"):
        filepath = os.path.join(DIR_SRT, filename)
        video_id = extract_video_id(filename)
        if video_id not in transcriptions_data:
            transcriptions_data[video_id] = {'vtt': None, 'whisper_srt': None}
        with open(filepath, 'r', encoding='utf-8') as f:
            transcriptions_data[video_id]['whisper_srt'] = f.read()

    if not transcriptions_data:
        logger.info("No hay subtítulos para procesar.")
        return

    if dry_run:
        logger.info(f"DRY RUN - Archivos procesados ({len(transcriptions_data)} videos encontrados):")
        for video_id, data in list(transcriptions_data.items())[:10]: 
            has_vtt = "SÍ" if data['vtt'] else "NO"
            has_srt = "SÍ" if data['whisper_srt'] else "NO"
            logger.info(f"Video ID: {video_id} -> VTT: {has_vtt} | SRT: {has_srt}")
        logger.info("Dry run completado. Base de datos no afectada.")
        return

    logger.info(f"Subiendo {len(transcriptions_data)} registros a Hostinger...")
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT
        )
        with connection.cursor() as cursor:
            # Precargar mapeo de youtube_id a id numérico
            cursor.execute("SELECT youtube_id, id FROM videos")
            video_mapping = {row[0]: row[1] for row in cursor.fetchall()}
            
            insert_query = """
                INSERT INTO transcriptions 
                (video_id, vtt, whisper_srt, language) 
                VALUES (%s, %s, %s, 'es')
                ON DUPLICATE KEY UPDATE
                vtt = VALUES(vtt),
                whisper_srt = VALUES(whisper_srt)
            """
            for yt_id, data in tqdm(transcriptions_data.items(), desc="Insertando BD"):
                numeric_id = video_mapping.get(yt_id)
                if numeric_id is None:
                    continue # El video no existe en Hostinger, se ignora de forma limpia
                    
                try:
                    cursor.execute(insert_query, (numeric_id, data['vtt'], data['whisper_srt']))
                except Exception as e:
                    logger.error(f"Error insertando YoutubeID {yt_id} (NumID {numeric_id}): {e}")
                    
        connection.commit()
        connection.close()
        logger.info("Migración a la base de datos completada exitosamente.")
    except Exception as e:
        logger.error(f"Error conectando a la BD: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migración VTT y SRT local a Hostinger")
    parser.add_argument('--dry-run', action='store_true', help="Solo lectura y consola sin guardar en DB")
    args = parser.parse_args()
    
    process_and_migrate_local(dry_run=args.dry_run)
