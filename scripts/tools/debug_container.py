import os
import pickle
import logging
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from sqlalchemy.orm import sessionmaker
from src.models import Video, get_engine
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugContainer")
load_dotenv()

DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
TOKEN_PATH = "token.pickle"

def test_drive():
    logger.info(f"Testing Drive with Folder ID: {DRIVE_FOLDER_ID}")
    if not os.path.exists(TOKEN_PATH):
        logger.error(f"TOKEN NOT FOUND at {TOKEN_PATH}")
        return
    
    with open(TOKEN_PATH, 'rb') as token:
        creds = pickle.load(token)
    
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    service = build('drive', 'v3', credentials=creds)
    query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, pageSize=10, fields="files(id, name)").execute()
    files = results.get('files', [])
    logger.info(f"DRIVE_FILES_FOUND: {len(files)}")
    for f in files:
        logger.info(f" - {f['name']}")

def test_db():
    logger.info("Testing DB Connection...")
    try:
        engine = get_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        count = db.query(Video).count()
        logger.info(f"DB_VIDEOS_COUNT: {count}")
        db.close()
    except Exception as e:
        logger.error(f"DB_ERROR: {e}")

if __name__ == "__main__":
    test_drive()
    test_db()
