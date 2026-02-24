import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

TOKEN_PATH = "token.pickle"

def find_parent_of_srts():
    with open(TOKEN_PATH, 'rb') as token:
        creds = pickle.load(token)
    service = build('drive', 'v3', credentials=creds)
    
    print("Searching for .srt files...")
    results = service.files().list(
        q="name contains '.srt' and trashed = false",
        pageSize=20,
        fields="files(name, parents)"
    ).execute()
    files = results.get('files', [])
    
    parents = {}
    for f in files:
        p = f.get('parents', ['None'])[0]
        parents[p] = parents.get(p, 0) + 1
        print(f"File: {f['name']} | Parent: {p}")
    
    print("\nParent distribution:")
    for p, count in parents.items():
        if p != 'None':
            # Get parent name
            try:
                folder = service.files().get(fileId=p, fields="name").execute()
                print(f"Folder: {folder['name']} | ID: {p} | Files found in sample: {count}")
            except:
                print(f"ID: {p} | Files found in sample: {count} (Name unknown)")

if __name__ == "__main__":
    find_parent_of_srts()
