import asyncio
from pyppeteer import launch
from pyppeteer_ghost_cursor import path
import json
import sys
import os

async def set_cookies(page, cookies_file):
    if not os.path.exists(cookies_file):
        return
    print(f"🍪 Importando cookies de {cookies_file}...")
    with open(cookies_file, 'r') as f:
        for line in f:
            if not line or line.startswith('#'): continue
            parts = line.strip().split('\t')
            if len(parts) < 7: continue
            cookie = {
                'name': parts[5],
                'value': parts[6],
                'domain': parts[0],
                'path': parts[2],
                'secure': parts[3].lower() == 'true',
                'httpOnly': False, # Netscape format doesn't explicitly store this
                'sameSite': 'Lax'
            }
            # Pyppeteer expects domain without leading dot sometimes, but let's try as is
            try:
                await page.setCookie(cookie)
            except: pass

async def solve_youtube(url):
    browser = await launch({
        'headless': True,
        'args': [
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        ]
    })
    
    page = await browser.newPage()
    await page.setViewport({'width': 1280, 'height': 720})
    await set_cookies(page, 'cookies.txt')
    
    # Interceptar peticiones para encontrar el stream de audio
    captured_urls = []
    
    async def intercept_response(res):
        if "googlevideo.com/videoplayback" in res.url:
            captured_urls.append(res.url)

    page.on('response', lambda res: asyncio.ensure_future(intercept_response(res)))

    try:
        print(f"🌐 Navegando a {url}...")
        await page.goto(url, {'waitUntil': 'domcontentloaded', 'timeout': 60000})
        
        # Guardar captura para depuración
        await page.screenshot({'path': 'bypass_screenshot.png'})
        print("📸 Captura de pantalla guardada en bypass_screenshot.png")
        
        # Manejar consentimiento de cookies si aparece
        try:
            # Esperar a que aparezca el diálogo de cookies
            await page.waitForSelector('form[action*="consent.youtube.com"] button', {'timeout': 5000})
            print("🍪 Diálogo de cookies detectado, aceptando...")
            await page.click('form[action*="consent.youtube.com"] button:nth-of-type(2)') # Usualmente el segundo es 'Aceptar todo'
            await asyncio.sleep(2)
        except:
            pass

        # Esperar a que el reproductor esté listo
        await page.waitForSelector('.html5-video-player', {'timeout': 10000})
        
        # Intentar clicar el play para forzar la carga del stream
        try:
            play_btn = await page.querySelector('.ytp-play-button')
            # Si tiene el título 'Reproducir' o no está en play, clicamos
            await page.click('.ytp-play-button')
            print("▶️ Play clicado")
            await asyncio.sleep(5)
        except: pass

        if captured_urls:
            print(f"🎯 {len(captured_urls)} URLs de media encontradas!")
            for u in captured_urls:
                if "mime=audio" in u:
                    return u
            return captured_urls[0]
        
        # Si no se encontró vía Network, intentar extraer del JS de la página
        print("🔍 Intentando extraer de ytInitialPlayerResponse...")
        try:
            player_response = await page.evaluate("() => window.ytInitialPlayerResponse")
            if player_response:
                streaming_data = player_response.get('streamingData', {})
                formats = streaming_data.get('adaptiveFormats', [])
                # Buscar el mejor formato de audio
                audio_formats = [f for f in formats if "audio/" in f.get('mimeType', '')]
                if audio_formats:
                    # El primero suele ser el mejor
                    best_audio = audio_formats[0]
                    url = best_audio.get('url')
                    if url:
                        print(f"🎯 URL de audio encontrada via JS!")
                        return url
                    elif 'signatureCipher' in best_audio:
                        print("⚠️ URL cifrada, intentando descifrar via JS...")
                        # Si está cifrada, es más complejo, pero a veces el navegador ya tiene la URL en otro lado
                        pass
        except Exception as e:
            print(f"❌ Error extrayendo JS: {e}")

        # Reintento final: esperar un poco más
        await asyncio.sleep(5)
        if audio_url:
            return audio_url
            
        print("❌ No se encontró URL de audio directa.")
        return None
            
    except Exception as e:
        print(f"❌ Error en bypass: {e}")
        return None
    finally:
        await browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 youtube_bypass.py <URL>")
        sys.exit(1)
    
    target_url = sys.argv[1]
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(solve_youtube(target_url))
    
    if result:
        # Imprimir solo la URL al final para que main.py pueda capturarla
        print(f"RESULT_URL:{result}")
    else:
        sys.exit(1)
