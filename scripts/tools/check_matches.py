import os
import pickle
from googleapiclient.discovery import build
from sqlalchemy.orm import sessionmaker
from src.models import Video, get_engine
from dotenv import load_dotenv

load_dotenv()
TOKEN_PATH = "token.pickle"
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

def check_intersection():
    with open(TOKEN_PATH, 'rb') as token:
        creds = pickle.load(token)
    service = build('drive', 'v3', credentials=creds)
    
    # 1. Get Drive files
    query = f"'{DRIVE_FOLDER_ID}' in parents and trashed = false"
    res = service.files().list(q=query, pageSize=1000, fields="files(id, name)").execute()
    drive_files = res.get('files', [])
    print(f"FILES IN DRIVE FOLDER: {len(drive_files)}")
    
    # 2. Get DB videos
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    videos = db.query(Video).order_by(Video.upload_date.desc()).limit(150).all()
    print(f"VIDEOS IN DB (RECENT): {len(videos)}")
    
    matches = 0
    for v in videos:
        found = False
        if v.transcription and v.transcription.srt_content:
            found = True
        else:
            for f in drive_files:
                if v.youtube_id in f['name']:
                    found = True
                    break
        if found:
            matches += 1
            if matches <= 5:
                print(f"MATCH: {v.youtube_id} -> {v.title}")
    
    print(f"TOTAL MATCHES: {matches}")
    db.close()

if __name__ == "__main__":
    check_intersection()
