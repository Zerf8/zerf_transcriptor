import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_message(text):
    if not TOKEN or not CHAT_ID:
        print("❌ Faltan credenciales de Telegram en .env")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print("✅ Mensaje enviado a Telegram.")
        else:
            print(f"❌ Error Telegram: {r.text}")
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")

if __name__ == "__main__":
    send_message("✅ **Proceso Completado**\n\nLa actualización de `lista_maestra_videos.txt` ha finalizado. Todos los videos deberían tener ahora su descripción.")
