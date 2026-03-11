"""
Este script reordena los IDs de los videos en la base de datos cronológicamente, 
basándose en la fecha de publicación original ('upload_date'). 
Ajusta de forma segura todos los IDs relacionados en tablas satélite (transcripciones, 
clips, stats) para preservar la integridad de los datos.
"""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def run_reorder():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "3306"))
    db_name = os.getenv("DB_NAME")

    print(f"Conectando a {host}...")
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=db_name,
        port=port,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cursor:
            # 1. Quitar las restricciones de Foreign Keys para poder mover IDs sin que MySQL aborte
            cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
            
            # 2. Configurar la tabla temporal para asignar el nuevo orden basado en 'upload_date'
            # Obtenemos TODOS los vídeos ordenador por FECHA de publicación vieja a nueva
            cursor.execute("SELECT id, youtube_id, upload_date FROM videos ORDER BY upload_date ASC, id ASC;")
            videos = cursor.fetchall()
            
            print(f"Reordenando {len(videos)} vídeos temporalmente...")
            # Pasamos todos los IDs a un rango seguro muy alto (>1000000) para no pisar claves
            for idx, video in enumerate(videos, 1):
                old_id = video['id']
                safe_id = 1000000 + idx
                
                # Mover 'videos'
                cursor.execute("UPDATE videos SET id=%s WHERE id=%s", (safe_id, old_id))
                # Todas sus tablas satélite
                cursor.execute("UPDATE video_stats SET video_id=%s WHERE video_id=%s", (safe_id, old_id))
                cursor.execute("UPDATE transcriptions SET video_id=%s WHERE video_id=%s", (safe_id, old_id))
                cursor.execute("UPDATE clips SET video_id=%s WHERE video_id=%s", (safe_id, old_id))
                cursor.execute("UPDATE comments SET video_id=%s WHERE video_id=%s", (safe_id, old_id))
                
            # Ahora tenemos todo en el rango 1000000+, los bajamos al rango 1, 2, 3...
            print("Aplicando IDs definitivos correlativos y cronológicos (1, 2, 3...)...")
            
            cursor.execute("SELECT id, youtube_id FROM videos ORDER BY id ASC;")
            safe_videos = cursor.fetchall()
            
            for idx, video in enumerate(safe_videos, 1):
                safe_id = video['id']
                new_id = idx # 1, 2, 3...
                
                cursor.execute("UPDATE videos SET id=%s WHERE id=%s", (new_id, safe_id))
                cursor.execute("UPDATE video_stats SET video_id=%s WHERE video_id=%s", (new_id, safe_id))
                cursor.execute("UPDATE transcriptions SET video_id=%s WHERE video_id=%s", (new_id, safe_id))
                cursor.execute("UPDATE clips SET video_id=%s WHERE video_id=%s", (new_id, safe_id))
                cursor.execute("UPDATE comments SET video_id=%s WHERE video_id=%s", (new_id, safe_id))
            
            # Resetear el AUTO_INCREMENT para los siguientes vídeos nuevos
            cursor.execute(f"ALTER TABLE videos AUTO_INCREMENT = {len(videos) + 1};")
            
            # Restaurar restricciones
            cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
            
        conn.commit()
        print("BBDD REORDENADA CON EXITO Y TODA LA CASCADA INTACTA!")
        
    except Exception as e:
        conn.rollback()
        print(f"Error durante reordenacion: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_reorder()
