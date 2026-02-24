import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

TOKEN_PATH = "token.pickle"

def list_folders():
    if not os.path.exists(TOKEN_PATH):
        print("TOKEN NOT FOUND")
        return
    
    with open(TOKEN_PATH, 'rb') as token:
        creds = pickle.load(token)
    
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    service = build('drive', 'v3', credentials=creds)
    
    results = service.files().list(
        q="mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        pageSize=100,
        fields="files(id, name)"
    ).execute()
    folders = results.get('files', [])
    
    print(f"--- FOLDERS FOUND ({len(folders)}) ---")
    for f in folders:
        print(f"NAME: {f['name']} | ID: {f['id']}")

if __name__ == "__main__":
    list_folders()
