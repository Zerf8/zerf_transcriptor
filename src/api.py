from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.models import get_engine, Video, VideoStats
from sqlalchemy.orm import sessionmaker
from typing import List
from pydantic import BaseModel
from datetime import datetime

# Pydantic Models (Schemas) for Response
class VideoSummary(BaseModel):
    id: int
    youtube_id: str
    title: str
    duration_string: str | None
    upload_date: datetime | None
    status: str

    class Config:
        orm_mode = True

class TranscriptionResponse(BaseModel):
    video_id: int
    text: str | None
    language: str
    
    class Config:
        orm_mode = True

class TranscriptionUpdate(BaseModel):
    text: str

class ClipResponse(BaseModel):
    id: int
    start_time: str
    end_time: str
    text_preview: str
    score: int
    reason: str
    
    class Config:
        orm_mode = True

app = FastAPI(title="Zerf Transcriptor API", version="1.0.0")

# Dependency
def get_db():
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Zerf Transcriptor API is running"}

@app.get("/videos", response_model=List[VideoSummary])
def get_videos(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Get a list of videos with pagination"""
    videos = db.query(Video).order_by(Video.upload_date.desc()).offset(skip).limit(limit).all()
    return videos

@app.get("/videos/{video_id}", response_model=VideoSummary)
def get_video(video_id: int, db: Session = Depends(get_db)):
    """Get a single video by ID"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@app.get("/videos/{video_id}/transcription", response_model=TranscriptionResponse)
def get_transcription(video_id: int, db: Session = Depends(get_db)):
    """Get method for transcription"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if transcription exists
    if not video.transcription:
         raise HTTPException(status_code=404, detail="Transcription not found")
    
    # Prefer Gemini text, fallback to Whisper
    text_content = video.transcription.gemini_text or video.transcription.whisper_text
    
    return TranscriptionResponse(
        video_id=video.id,
        text=text_content,
        language=video.transcription.language
    )

@app.put("/videos/{video_id}/transcription")
def update_transcription(video_id: int, update_data: TranscriptionUpdate, db: Session = Depends(get_db)):
    """Update transcription text"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video or not video.transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
    
    # Update text (we update gemini_text as the 'refined' version)
    video.transcription.gemini_text = update_data.text
    db.commit()
    
    return {"status": "updated", "video_id": video.id}

@app.get("/videos/{video_id}/clips", response_model=List[ClipResponse])
def get_video_clips(video_id: int, db: Session = Depends(get_db)):
    """Get clips for a video"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    return video.clips
