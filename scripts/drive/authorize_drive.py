import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Si modificas estos alcances, elimina el archivo token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

def main():
    creds = None
    # El archivo token.pickle almacena los tokens de acceso y refresco del usuario.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # Si no hay credenciales válidas disponibles, deja que el usuario inicie sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secrets.json'):
                print("Error: No se encontró 'client_secrets.json'.")
                print("Por favor, descárgalo de Google Cloud Console (OAuth 2.0 Client ID) y colócalo en esta carpeta.")
                return

            flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Guardar las credenciales para la próxima ejecución
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)

    # Probar la conexión buscando la carpeta SRT_YouTube
    results = service.files().list(
        q="name = 'SRT_YouTube' and mimeType = 'application/vnd.google-apps.folder'",
        spaces='drive',
        fields='files(id, name)').execute()
    items = results.get('files', [])

    if not items:
        print('No se encontró la carpeta SRT_YouTube en Google Drive.')
    else:
        print('Carpeta encontrada:')
        for item in items:
            print(f"{item['name']} ({item['id']})")
            print(f"\n¡Éxito! Copia este ID y ponlo en tu .env como DRIVE_FOLDER_ID={item['id']}")

if __name__ == '__main__':
    main()
