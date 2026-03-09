import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Video
from datetime import datetime

load_dotenv()
DB_USER = os.getenv('DB_USER', 'u316279147_transcriptor')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST', '51.49.135.18')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_NAME = os.getenv('DB_NAME', 'u316279147_transcriptor')
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if __name__ == "__main__":
    session = SessionLocal()
    vid_id = "FhXZBaz_ph8"
    
    existing = session.query(Video).filter(Video.youtube_id == vid_id).first()
    
    if not existing:
        print(f"   ✨ ¡Insertando VÍDEO forzoso en BD_HOSTINGER...")
        new_vid = Video(
             youtube_id=vid_id,
             title="ATHLETIC 0 FC BARCELONA 1 DIFÍCIO",
             channel="ZerfFCB",
             upload_date=datetime.now(),
             duration=600,
             status='pending'
        )
        session.add(new_vid)
        session.commit()
        print("✅ Insertado con éxito")
    else:
        print("✅ Ya existe")
    session.close()
