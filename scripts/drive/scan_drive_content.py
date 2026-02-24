import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

TOKEN_PATH = "token.pickle"

def find_rich_folder():
    with open(TOKEN_PATH, 'rb') as token:
        creds = pickle.load(token)
    service = build('drive', 'v3', credentials=creds)
    
    print("Searching for folders...")
    folders_res = service.files().list(
        q="mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        pageSize=100,
        fields="files(id, name)"
    ).execute()
    folders = folders_res.get('files', [])
    
    for f in folders:
        # Count SRTs in this folder
        q = f"'{f['id']}' in parents and (name contains '.srt' or mimeType = 'text/plain') and trashed = false"
        res = service.files().list(q=q, pageSize=10).execute()
        count = len(res.get('files', []))
        if count > 0:
            print(f"FOLDER: {f['name']} | ID: {f['id']} | SRT_SAMPLES: {count}")
            # If we find more than a few, let's explore it
            if count >= 3:
                print(f"  Sample files in {f['name']}: {[x['name'] for x in res['files'][:3]]}")

if __name__ == "__main__":
    find_rich_folder()
