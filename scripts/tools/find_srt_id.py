import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

TOKEN_PATH = "token.pickle"

def find_srt_folder():
    if not os.path.exists(TOKEN_PATH):
        print("TOKEN NOT FOUND")
        return
    
    with open(TOKEN_PATH, 'rb') as token:
        creds = pickle.load(token)
    
    service = build('drive', 'v3', credentials=creds)
    
    results = service.files().list(
        q="name contains 'SRT_YouTube' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)"
    ).execute()
    folders = results.get('files', [])
    
    if not folders:
        print("SRT_YouTube folder NOT FOUND")
        # Try a broader search just in case
        results = service.files().list(
            q="name contains 'SRT' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id, name)"
        ).execute()
        folders = results.get('files', [])
        print("Folders with 'SRT' in name:")
        for f in folders:
            print(f"NAME: {f['name']} | ID: {f['id']}")
    else:
        for f in folders:
            print(f"MATCH FOUND: {f['name']} | ID: {f['id']}")

if __name__ == "__main__":
    find_srt_folder()
