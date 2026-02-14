
import os
import requests
from dotenv import load_dotenv

def send_telegram_message(message: str):
    """Envía un mensaje a Telegram usando las credenciales del .env"""
    # Cargar .env por si acaso no está cargado
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("⚠️ Telegram no configurado. Falta TOKEN o CHAT_ID en .env")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✉️ Notificación enviada a Telegram.")
            return True
        else:
            print(f"❌ Error enviando a Telegram: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error de conexión con Telegram: {e}")
        return False

if __name__ == "__main__":
    # Prueba rápida
    send_telegram_message("🚀 *Zerf Transcriptor*:\nPrueba de conexión activada.")
