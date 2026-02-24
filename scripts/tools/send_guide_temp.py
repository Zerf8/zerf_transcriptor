import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GUIDE_PATH = r"C:\Users\Usuario\.gemini\antigravity\brain\78bdf01f-c5bc-4a33-b23a-e0bb1baa7915\setup_guide.md"

def send_plain_message(text):
    if not TOKEN or not CHAT_ID:
        print("❌ Faltan credenciales")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        # "parse_mode": "Markdown"  <-- Removed to avoid errors
    }
    
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print("✅ Mensaje enviado.")
        else:
            print(f"❌ Error Telegram: {r.text}")
    except Exception as e:
        print(f"❌ Error enviando: {e}")

try:
    with open(GUIDE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    header = "📄 **Guía de Instalación (Zerf Transcriptor)**\n\n"
    full_message = header + content
    
    print(f"Sending message of length {len(full_message)}...")
    send_plain_message(full_message)
except Exception as e:
    print(f"Error: {e}")
