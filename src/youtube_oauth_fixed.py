import json
import time
import urllib.request
import urllib.parse
import uuid
import os
from datetime import datetime, timezone

# Credenciales oficiales de YouTube TV (TVHTML5)
_CLIENT_ID = '861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com'
_CLIENT_SECRET = 'SboVhoG9s0rNafixCSGGKXAT'
_SCOPES = 'http://gdata.youtube.com https://www.googleapis.com/auth/youtube'
CACHE_DIR = os.path.expanduser('~/.cache/yt-dlp/youtube-oauth2')
CACHE_FILE = os.path.join(CACHE_DIR, 'token_data.json')

def post_json(url, data):
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def authorize():
    print("🔑 Iniciando flujo de autorización OAuth2 (Modo TV)...")
    try:
        code_response = post_json('https://www.youtube.com/o/oauth2/device/code', {
            'client_id': _CLIENT_ID,
            'scope': _SCOPES,
            'device_id': uuid.uuid4().hex,
            'device_model': 'ytlr::'
        })
        
        verification_url = code_response['verification_url']
        user_code = code_response['user_code']
        interval = code_response.get('interval', 5)
        device_code = code_response['device_code']
        
        print("\n" + "="*50)
        print(f"👉 Ve a: {verification_url}")
        print(f"👉 Introduce este código: {user_code}")
        print("="*50 + "\n")
        print("Esperando autorización...")
        
        while True:
            try:
                token_response = post_json('https://www.youtube.com/o/oauth2/token', {
                    'client_id': _CLIENT_ID,
                    'client_secret': _CLIENT_SECRET,
                    'code': device_code,
                    'grant_type': 'http://oauth.net/grant_type/device/1.0'
                })
                
                if 'access_token' in token_response:
                    token_response['expires_at'] = time.time() + token_response['expires_in']
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    with open(CACHE_FILE, 'w') as f:
                        json.dump(token_response, f)
                    print("✅ ¡Autorización completada con éxito!")
                    return token_response
                    
            except urllib.error.HTTPError as e:
                resp = json.loads(e.read().decode('utf-8'))
                error = resp.get('error')
                if error == 'authorization_pending':
                    time.sleep(interval)
                    continue
                else:
                    print(f"❌ Error OAuth: {error}")
                    return None
    except Exception as e:
        print(f"❌ Error crítico en OAuth: {e}")
        return None

def get_token():
    if not os.path.exists(CACHE_FILE):
        return authorize()
    
    with open(CACHE_FILE, 'r') as f:
        token_data = json.load(f)
    
    if token_data.get('expires_at', 0) < time.time() + 60:
        print("🔄 Refrescando token expirado...")
        try:
            token_response = post_json('https://www.youtube.com/o/oauth2/token', {
                'client_id': _CLIENT_ID,
                'client_secret': _CLIENT_SECRET,
                'refresh_token': token_data['refresh_token'],
                'grant_type': 'refresh_token'
            })
            token_response['expires_at'] = time.time() + token_response['expires_in']
            # Mantener el refresh_token si no viene uno nuevo
            if 'refresh_token' not in token_response:
                token_response['refresh_token'] = token_data['refresh_token']
            
            with open(CACHE_FILE, 'w') as f:
                json.dump(token_response, f)
            return token_response
        except:
            return authorize()
    
    return token_data

if __name__ == "__main__":
    get_token()
