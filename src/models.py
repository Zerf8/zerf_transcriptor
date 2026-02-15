from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Video(Base):
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True)
    youtube_id = Column(String(50), unique=True, nullable=False)
    title = Column(String(255))
    duration = Column(Integer)  # en segundos
    duration_string = Column(String(20)) # HH:MM:SS
    upload_date = Column(DateTime)
    channel = Column(String(100))
    description = Column(Text)
    thumbnail = Column(String(255))
    tags = Column(Text) # Tags separados por comas
    category = Column(String(50))
    is_live = Column(Integer, default=0) # 0 o 1
    status = Column(String(20), default='pending') # pending, processing, completed, failed
    last_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    stats = relationship("VideoStats", back_populates="video", uselist=False, cascade="all, delete-orphan")
    transcription = relationship("Transcription", back_populates="video", uselist=False, cascade="all, delete-orphan")
    clips = relationship("Clip", back_populates="video", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="video", cascade="all, delete-orphan")

class VideoStats(Base):
    __tablename__ = 'video_stats'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False)
    view_count = Column(Integer)
    like_count = Column(Integer)
    comment_count = Column(Integer)
    subscriber_count = Column(Integer)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    video = relationship("Video", back_populates="stats")

class Transcription(Base):
    __tablename__ = 'transcriptions'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False)
    whisper_text = Column(Text(4294967295)) # LongText
    gemini_text = Column(Text(4294967295))  # LongText
    srt_content = Column(Text(4294967295))  # LongText
    raw_json = Column(Text(4294967295))     # El JSON bruto de Whisper
    language = Column(String(10), default='es')
    
    video = relationship("Video", back_populates="transcription")

class Clip(Base):
    __tablename__ = 'clips'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False)
    start_time = Column(String(20)) # HH:MM:SS
    end_time = Column(String(20))
    start_seconds = Column(Float)
    end_seconds = Column(Float)
    text_preview = Column(Text)
    score = Column(Integer)
    reason = Column(String(255))
    tags = Column(String(255)) # Separados por comas o JSON
    source = Column(String(20)) # 'rules' o 'ai'
    
    video = relationship("Video", back_populates="clips")

class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False)
    comment_id = Column(String(100), unique=True)
    author = Column(String(255))
    text = Column(Text)
    like_count = Column(Integer)
    timestamp = Column(DateTime)
    
    video = relationship("Video", back_populates="comments")

class DictionaryEntry(Base):
    __tablename__ = 'dictionary'
    
    id = Column(Integer, primary_key=True)
    term = Column(String(100), unique=True, nullable=False)
    correction = Column(String(100))
    category = Column(String(50)) # 'nombre', 'termino', 'equipo', etc.

# Utilidad de conexión
def get_engine():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME")
    
    # Prevenir errores de caracteres especiales en el password
    import urllib.parse
    safe_password = urllib.parse.quote_plus(password)
    
    connection_string = f"mysql+pymysql://{user}:{safe_password}@{host}:{port}/{db_name}"
    return create_engine(connection_string, pool_recycle=3600)

def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("✓ Base de datos inicializada (Tablas creadas)")

if __name__ == "__main__":
    init_db()
