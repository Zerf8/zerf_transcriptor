import os
import sys
import subprocess

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from dotenv import load_dotenv
from src.models import get_engine, Video
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

load_dotenv()

def backup_db():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME")
    
    backup_file = os.path.join(os.path.dirname(__file__), "backup_before_reorder.sql")
    print(f"Creando copia de seguridad de la BD: {db_name} en {backup_file}...")
    
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password
    cmd = ["mysqldump", "--column-statistics=0", "-h", host, "-P", port, "-u", user, db_name]
    
    try:
        with open(backup_file, "w") as f:
            subprocess.run(cmd, env=env, stdout=f, check=True)
        print("✅ Copia de seguridad completada con éxito.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al hacer la copia de seguridad: {e}")
        sys.exit(1)

def reorder_ids():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Calculando nuevo mapeo de IDs cronológicos...")
    videos = session.query(Video).order_by(Video.upload_date.asc()).all()
    
    mapping = []
    for i, video in enumerate(videos):
        new_id = i + 1
        if video.id != new_id:
            mapping.append({
                "old_id": video.id,
                "new_id": new_id,
                "temp_id": new_id + 1000000
            })
    
    session.close()

    if not mapping:
        print("✅ Todos los vídeos ya están perfectamente ordenados.")
        return

    print(f"Iniciando reemplazo transaccional de {len(mapping)} IDs incorrectos...")
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        
        tables_with_video_id = [
            "video_stats",
            "transcriptions",
            "clips",
            "comments",
            "video_entities"
        ]
        
        try:
            # 1. Shift to generic temp IDs
            for m in mapping:
                for table in tables_with_video_id:
                    conn.execute(text(f"UPDATE {table} SET video_id = :temp_id WHERE video_id = :old_id"), {"temp_id": m["temp_id"], "old_id": m["old_id"]})
                
                conn.execute(text(f"UPDATE videos SET id = :temp_id WHERE id = :old_id"), {"temp_id": m["temp_id"], "old_id": m["old_id"]})
            
            # 2. Shift from generic temp IDs to correct new IDs
            for m in mapping:
                for table in tables_with_video_id:
                    conn.execute(text(f"UPDATE {table} SET video_id = :new_id WHERE video_id = :temp_id"), {"new_id": m["new_id"], "temp_id": m["temp_id"]})
                
                conn.execute(text(f"UPDATE videos SET id = :new_id WHERE id = :temp_id"), {"new_id": m["new_id"], "temp_id": m["temp_id"]})
            
            # Update AUTO_INCREMENT value
            max_id = len(videos) + 1
            conn.execute(text(f"ALTER TABLE videos AUTO_INCREMENT = {max_id}")) # this isn't strictly parameterizable like this but it's safe since it's hardcoded to len
            
            print(f"✅ ¡{len(mapping)} vídeos modificados correctamente!")
        except Exception as e:
            print(f"❌ Error durante el reemplazo: {e}")
            raise e
        finally:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

if __name__ == "__main__":
    backup_db()
    reorder_ids()
