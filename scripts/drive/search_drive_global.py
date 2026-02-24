import os
import pickle
import logging
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DriveSearch")
load_dotenv()

TOKEN_PATH = "token.pickle"

def find_any_srt():
    if not os.path.exists(TOKEN_PATH):
        print("TOKEN NOT FOUND")
        return
    
    with open(TOKEN_PATH, 'rb') as token:
        creds = pickle.load(token)
    
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    service = build('drive', 'v3', credentials=creds)
    
    print("Searching for any .srt files in the entire Drive...")
    results = service.files().list(
        q="name contains '.srt' and trashed = false",
        pageSize=10,
        fields="files(id, name, parents)"
    ).execute()
    files = results.get('files', [])
    
    print(f"Found {len(files)} .srt files.")
    for f in files:
        print(f" - {f['name']} (ID: {f['id']}, Parent: {f.get('parents', ['None'])[0]})")

    print("\nSearching for folder 'SRT_YouTube'...")
    folders = service.files().list(
        q="name = 'SRT_YouTube' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)"
    ).execute().get('files', [])
    for folder in folders:
        print(f"Folder found: {folder['name']} (ID: {folder['id']})")

if __name__ == "__main__":
    find_any_srt()
