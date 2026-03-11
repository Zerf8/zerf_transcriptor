"""
Este script se encarga de modificar la descripción de los videos de YouTube para añadir 
un bloque de texto promocional (enlaces a redes sociales y Patreon). También intenta añadir 
este mismo texto como un comentario destacado en los videos procesados. Opera sobre los 
videos que están en la base de datos y que aún no contengan el texto clave.
"""
import os
import time
import pickle
import logging
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from sqlalchemy.orm import sessionmaker
from src.models import Video, get_engine
from dotenv import load_dotenv

load_dotenv()

CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_PICKLE_FILE = "token.pickle"

SOCIAL_MEDIA_FOOTER = """
⎯⎯⎯⎯⎯ APOYA EL CANAL ⎯⎯⎯⎯⎯
Házte PATREON desde 10 céntimos al día, APOYA y vive el Barça desde nuestro canal de WhatsApp EXCLUSIVO para Patreons 👋▶ https://www.patreon.com/cw/ZerfFCB

⎯⎯⎯⎯⎯ SÍGUEME EN REDES ⎯⎯⎯⎯⎯
🐦 X (Twitter): https://www.x.com/ZerfBarbut
📸 Instagram: https://www.instagram.com/zerf_fcb/
💬 Canal WhatsApp: https://whatsapp.com/channel/0029VbBBxBa2v1Ik4095g20d
"""

# Configurar logging a archivo
logging.basicConfig(
    filename='social_media_update.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_youtube_service():
    """Autentica y devuelve el servicio de YouTube API."""
    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
    creds = None
    
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                raise FileNotFoundError(f"No se encontró {CLIENT_SECRETS_FILE}.")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            pickle.dump(creds, token)
            
    return build("youtube", "v3", credentials=creds)

def add_social_footer_to_videos():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        youtube = get_youtube_service()

        print("Obteniendo todos los videos de la base de datos...")
        logging.info("--- NUEVA EJECUCIÓN DEL SCRIPT ---")
        # Por defecto los queremos procesar desde los MÁS NUEVOS a los más antiguos
        all_videos = session.query(Video).filter(~Video.description.like('%APOYA EL CANAL%')).order_by(Video.upload_date.desc()).limit(10).all()
        total = len(all_videos)
        print(f"Encontrados {total} vídeos. Empezando por los MÁS NUEVOS.")
        logging.info(f"Encontrados {total} vídeos. Empezando por los MÁS NUEVOS.")

        for i, video in enumerate(all_videos, 1):
            yid = video.youtube_id
            msg = f"[{i}/{total}] Procesando: {video.title} ({yid})"
            print(msg)
            logging.info(msg)

            # 1. ACTUALIZAR DESCRIPCIÓN
            try:
                # Obtener la descripción actual real de youtube
                video_res = youtube.videos().list(part="snippet", id=yid).execute()
                if not video_res.get('items'):
                    print(f"  ⚠️ No se encontró el vídeo en YouTube.")
                    logging.warning(f"Vídeo no encontrado en YouTube: {yid}")
                    continue
                
                snippet = video_res['items'][0]['snippet']
                current_desc = snippet.get('description', '')
                
                if "APOYA EL CANAL" not in current_desc:
                    print("  📝 Añadiendo footer a la descripción...")
                    new_desc = current_desc.strip() + "\n\n" + SOCIAL_MEDIA_FOOTER.strip()
                    
                    # Actualizar en YouTube
                    youtube.videos().update(
                        part="snippet",
                        body={
                            "id": yid,
                            "snippet": {
                                "title": snippet['title'],
                                "description": new_desc,
                                "categoryId": snippet.get('categoryId', '17')
                            }
                        }
                    ).execute()
                    
                    # Actualizar en BBDD local
                    video.description = new_desc
                    session.commit()
                    logging.info(f"✅ Descripción actualizada: {yid}")
                else:
                    print("  ✅ La descripción ya tiene el footer.")
                    logging.info(f"✅ Omitido, ya tenía footer: {yid}")
            except Exception as e:
                print(f"  ❌ Error actualizando descripción: {e}")
                logging.error(f"Error descripción en {yid}: {e}")

            # 2. AÑADIR COMENTARIO FIJADO
            try:
                # Buscar si ya hay un comentario anclado o si ya hemos puesto este comentario
                threads_res = youtube.commentThreads().list(
                    part="snippet",
                    videoId=yid,
                    maxResults=5, # Comprobar los primeros
                    order="relevance" # Para que salga el pinned arriba
                ).execute()

                already_commented = False
                for thread in threads_res.get('items', []):
                    top_comment = thread['snippet']['topLevelComment']['snippet']
                    # Validar si el comentario es nuestro y si tiene el texto
                    if "APOYA EL CANAL" in top_comment['textOriginal']:
                        already_commented = True
                        break

                if not already_commented:
                    print("  💬 Añadiendo comentario fijado...")
                    # Crear comentario
                    comment_res = youtube.commentThreads().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "videoId": yid,
                                "topLevelComment": {
                                    "snippet": {
                                        "textOriginal": SOCIAL_MEDIA_FOOTER.strip()
                                    }
                                }
                            }
                        }
                    ).execute()
                    
                    # Fijar el comentario (Requiere setModerationStatus pero no se puede hacer pin directamente a través de API)
                    # NOTA: La YouTube Data API NO SOPORTA PINNEAR comentarios actualmente.
                    # Quedará como un comentario del canal (con corona), pero no "Pinned".
                    print("  ✅ Comentario añadido (Nota: La API de YouTube no permite hacer 'Pin' automáticamente).")
                    logging.info(f"✅ Comentario añadido: {yid}")
                else:
                    print("  ✅ El comentario ya existe.")
                    logging.info(f"✅ Omitido, ya tenía comentario: {yid}")
            except Exception as e:
                print(f"  ❌ Error añadiendo comentario: {e}")
                logging.error(f"Error comentario en {yid}: {e}")

            print("---")
            time.sleep(1) # Respetar cuota API
            
    except Exception as e:
        print(f"Error general: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    add_social_footer_to_videos()
