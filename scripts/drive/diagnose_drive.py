import os
import pickle
import logging
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

TOKEN_PATH = "token.pickle"
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

def diagnose_drive_matching():
    if not os.path.exists(TOKEN_PATH):
        print("TOKEN NOT FOUND")
        return
    
    with open(TOKEN_PATH, 'rb') as token:
        creds = pickle.load(token)
    
    service = build('drive', 'v3', credentials=creds)
    
    print(f"Checking FOLDER_ID: {DRIVE_FOLDER_ID}")
    
    # List files in the configured folder
    query = f"'{DRIVE_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, pageSize=20, fields="files(id, name)").execute()
    files = results.get('files', [])
    
    print(f"Files found in folder ({len(files)}):")
    for f in files:
        print(f" - NAME: {f['name']} | ID: {f['id']}")

    # Search for SRT_YouTube folder globally to verify ID
    print("\nSearching for folder 'SRT_YouTube' globally...")
    folders = service.files().list(
        q="name = 'SRT_YouTube' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    ).execute().get('files', [])
    for folder in folders:
        print(f"Folder found: {folder['name']} | ID: {folder['id']}")

if __name__ == "__main__":
    diagnose_drive_matching()
