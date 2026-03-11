"""
Este script busca y elimina registros duplicados en la tabla 'transcriptions' 
para un mismo 'video_id'. En caso de encontrar duplicados, conserva preferentemente 
aquel que tenga un archivo SRT ('whisper_srt') o en su defecto un VTT, 
eliminando los restantes para mantener la integridad de la base de datos.
"""
import os
import pymysql
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RemoveDuplicates")

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = int(os.getenv("DB_PORT", 3306))

def remove_duplicates():
    logger.info("Iniciando busqueda de duplicados en la tabla transcriptions...")
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT
        )
        
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Encontramos video_ids duplicados
            cursor.execute("SELECT video_id, COUNT(*) as c FROM transcriptions GROUP BY video_id HAVING c > 1")
            duplicates = cursor.fetchall()
            
            if not duplicates:
                logger.info("No se encontraron transcripciones duplicadas para el mismo video_id.")
                return
                
            logger.info(f"Se encontraron {len(duplicates)} video_id con múltiples registros.")
            
            deleted_count = 0
            
            for dup in duplicates:
                vid = dup['video_id']
                # Obtenemos todos los registros para ese video_id
                cursor.execute("SELECT id, video_id, whisper_srt, vtt FROM transcriptions WHERE video_id = %s", (vid,))
                rows = cursor.fetchall()
                
                # Ordenamos para darle prioridad al que tenga whisper_srt, luego vtt
                def sort_key(row):
                    has_srt = bool(row['whisper_srt'])
                    has_vtt = bool(row['vtt'])
                    return (has_srt, has_vtt)
                    
                rows.sort(key=sort_key, reverse=True)
                
                # El mejor candidato a conservar
                best_row = rows[0]
                rows_to_delete = rows[1:]
                
                logger.info(f"Video_id {vid}: Conservando ID {best_row['id']} (SRT: {bool(best_row['whisper_srt'])}, VTT: {bool(best_row['vtt'])}). Eliminando {len(rows_to_delete)} duplicados.")
                
                for r in rows_to_delete:
                    cursor.execute("DELETE FROM transcriptions WHERE id = %s", (r['id'],))
                    deleted_count += 1
                    
        connection.commit()
        connection.close()
        logger.info(f"Proceso completado. Se han eliminado {deleted_count} registros redundantes.")
        
    except Exception as e:
        logger.error(f"Error conectando a la BD o durante el proceso: {e}")

if __name__ == "__main__":
    remove_duplicates()
