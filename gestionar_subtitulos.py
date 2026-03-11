# -*- coding: utf-8 -*-
"""
gestionar_subtitulos.py

Gestor para:
1. Traducir SRTs usando la API de Gemini.
2. Subir SRTs a YouTube (requiere client_secrets.json y flujo OAuth).
3. Gestionar subtítulos en la base de datos local.

Uso:
    # Traducir un vídeo a inglés
    python gestionar_subtitulos.py --video ID --translate en

    # Subir un SRT a YouTube
    python gestionar_subtitulos.py --video ID --upload
"""

import os
import sys
import argparse
import time
import json
from datetime import datetime

import google.generativeai as genai
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# YouTube API imports
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import pickle

load_dotenv()

# ── Configuración Gemini ──────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ── Rutas ──────────────────────────────────────────────────────────────────────
CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_PICKLE_FILE = "token.pickle"
SRT_DIR = r"G:\Mi unidad\Transcripts_Barca\SRT_YouTube"

# ── Modelos ────────────────────────────────────────────────────────────────────
from src.models import Video, Transcription, get_engine

# ── TRADUCCIÓN CON GEMINI ─────────────────────────────────────────────────────
def traducir_srt_gemini(srt_content: str, target_language: str) -> str:
    """Traduce o refina un contenido SRT de forma SEGURA para evitar corrupción de tiempos."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no configurado en el archivo .env")

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # --- PARSEO DE SRT ---
    import re
    blocks = []
    # Dividir por bloques (número, tiempo, texto)
    raw_blocks = re.split(r'\n\n+', srt_content.strip())
    for rb in raw_blocks:
        lines = rb.strip().split('\n')
        if len(lines) >= 2:
            idx = lines[0]
            time_line = lines[1]
            text = " ".join(lines[2:])
            blocks.append({"index": idx, "time": time_line, "text": text})

    if not blocks:
        return srt_content

    # Preparar el contenido para Gemini (Lista numerada)
    text_list = "\n".join([f"[{b['index']}]: {b['text']}" for b in blocks])
    
    is_refinement = target_language.lower() == 'es' or target_language.lower() == 'spanish'

    prompt = f"""
    Eres un experto en edición de subtítulos de fútbol (FC Barcelona). 
    Tu tarea es {'REFINAR Y CORREGIR' if is_refinement else 'TRADUCIR'} la siguiente lista de subtítulos al idioma: {target_language}.
    
    REGLAS CRÍTICAS:
    1. DEVUELVE EXACTAMENTE EL MISMO NÚMERO DE LÍNEAS.
    2. Mantén el formato '[ID]: Texto'. No omitas ninguna línea ni fusiones bloques.
    3. REGLAS DE CONTENIDO:
       - SALUDO: Si al principio del vídeo el presentador dice algo parecido a "Hola Culerada", corrígelo a la escritura exacta: "Hola Culerada, Hola Zerfistas". Si empieza hablando de otra cosa o dice otra frase, NO añadas el saludo; deja su frase tal cual.
       - DESPEDIDA: "Força Barça" (si aparece hacia el final).
       - TÉRMINOS: "Joan" (portero), "Camp Nou", "Nou Camp Nou", "Primera División", "portería a cero", "nos han hecho una ocasión", "entrando desde atrás", "aposta", "Sed buenos".
    4. FIDELIDAD ABSOLUTA: No repitas el saludo en el bloque [2] ni reemplaces el texto original por el saludo. Cada [ID] debe contener la versión refinada de SU texto original, sin omitir información.
    5. CORRECCIONES FIJAS (Errores de Whisper):
       - Si dice "tele y ahí" o similar, cámbialo por "tele y dices hostia".
       - Si dice "vamos. Buenos." o "vamos Buenos.", cámbialo por "vamos. Sed buenos.".
    6. ESTADIO: NUNCA cambies "Camp Nou" o "CN" por "Johan Cruyff". Si dice Camp Nou, se queda como Camp Nou.
    7. NO INVENTAR: No cambies nombres de jugadores ni de estadios que ya estén bien en la transcripción.
    8. NO CENSURA: MANTÉN el lenguaje informal, apasionado y crudo. Si el hablante dice "puto loco", "joder", "hostia", etc., NO lo suavices ni lo quites. Queremos el tono auténtico del Zerfista.
    9. Si hay ruido como "[ __ ]" o "trices", límpialo o interprétalo según el contexto pero MANTÉN LA LÍNEA.
    
    CONTENIDO A PROCESAR:
    {text_list}
    """
    
    print(f"   [AI] {'Refinamiento' if is_refinement else 'Traducción'} seguro en curso ({len(blocks)} bloques)...")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        print("   [NETWORK] Conectando con Gemini API v1beta...")
        resp = requests.post(url, headers=headers, json=payload, verify=False, timeout=180)
        print(f"   [NETWORK] Respuesta recibida HTTP {resp.status_code}")
        
        resp_json = resp.json()
        
        if 'error' in resp_json:
            raise ValueError(f"Error de API Gemini: {resp_json['error']}")
            
        generated_text = resp_json['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        raise ValueError(f"Fallo contactando con Gemini REST API: {e}")
    
    # --- RE-ENSAMBLAJE DE SRT ---
    generated_text = generated_text.strip()
    
    # Limpiar posible markdown
    if generated_text.startswith("```"): 
        generated_text = generated_text.split("\n", 1)[-1]
    if generated_text.endswith("```"):
        generated_text = generated_text.rsplit("\n", 1)[0]
    generated_text = generated_text.replace("```srt", "").replace("```", "").strip()

    id_to_text = {}
    
    # Intentar parsear como SRT estándar o como lista de IDs
    gen_blocks = re.split(r'\n\n+', generated_text)
    for gb in gen_blocks:
        lines = gb.strip().split('\n')
        if len(lines) >= 3 and '-->' in lines[1]:
            # Formato SRT detectado
            idx = lines[0].strip()
            text = " ".join(lines[2:]).strip()
            id_to_text[idx] = text
        else:
            # Fallback Linea por Linea (para formato [1]: texto)
            for line in lines:
                match = re.match(r'\[?(\d+)\]?:?\s*(.*)', line.strip())
                if match and match.group(2):
                    id_to_text[match.group(1)] = match.group(2).strip()

    # Construir el SRT final usando TIEMPOS ORIGINALES
    output = []
    for b in blocks:
        str_idx = str(b['index'])
        refined_text = id_to_text.get(str_idx, b['text']) # Fallback al original si falla
        # Limpiar posibles restos numéricos si se colaron
        refined_text = re.sub(r'^\[\d+\]:?\s*', '', refined_text).strip()
        
        output.append(str_idx)
        output.append(b['time'])
        output.append(refined_text)
        output.append("")

    return "\n".join(output)

def traducir_metadatos_gemini(title: str, description: str, target_language: str) -> dict:
    """Traduce el título y la descripción al idioma objetivo usando Gemini."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no configurado en el archivo .env")

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Eres un traductor profesional de contenidos de YouTube del FC Barcelona.
    Traduce el siguiente Título y Descripción del vídeo del español al idioma: {target_language}.
    
    REGLAS:
    1. Mantén un tono informal, apasionado y futbolero.
    2. Convierte "Barça" y "FC Barcelona" a su forma natural en el idioma destino.
    3. Conserva los emojis, enlaces y hashtags exactamente donde están.
    4. Devuelve un objeto JSON con las claves "title" y "description".
    
    TÍTULO ORIGINAL:
    {title}
    
    DESCRIPCIÓN ORIGINAL:
    {description}
    """
    
    print(f"   [AI] Traduciendo Título y Descripción a {target_language}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    try:
        import requests
        resp = requests.post(url, headers=headers, json=payload, verify=False)
        resp_json = resp.json()
        
        if 'error' in resp_json:
            raise ValueError(f"Error de API Gemini: {resp_json['error']}")
            
        generated_text = resp_json['candidates'][0]['content']['parts'][0]['text']
        return json.loads(generated_text)
    except Exception as e:
        print(f"   [ERROR AI] Fallo traduciendo metadatos: {e}")
        # Retornar texto básico con sufijo en caso de error
        return {
            "title": f"[EN] {title}"[:100], 
            "description": f"Translated description for: {title}\n\n{description}"
        }


# ── GENERACIÓN DE DESCRIPCIÓN ──────────────────────────────────────────────────
def limpiar_srt_para_ia(srt_content: str) -> str:
    """Limpia un SRT de tiempos e índices para dejar solo el texto fluido."""
    import re
    # Eliminar líneas de tiempo (00:00:00,000 --> 00:00:00,000)
    text = re.sub(r'\d{2}:\d{2}:\d{2}[,.]\d{3} --> \d{2}:\d{2}:\d{2}[,.]\d{3}', '', srt_content)
    # Eliminar índices numéricos al principio de línea
    text = re.sub(r'^\d+$\n', '', text, flags=re.MULTILINE)
    # Eliminar tags de formato (<c>, etc)
    text = re.sub(r'<[^>]+>', '', text)
    # Eliminar saltos de línea excesivos
    text = re.sub(r'\n+', ' ', text)
    return text.strip()

def generar_descripcion_gemini(srt_content: str) -> str:
    """Genera una descripción optimizada para YouTube basada en los subtítulos."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no configurado.")

    # Usar el nombre de modelo más estándar
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    texto_limpio = limpiar_srt_para_ia(srt_content)
    
    # Links auténticos del usuario (según pipeline_architecture.md)
    patreon = "https://www.patreon.com/cw/ZerfFCB"
    twitter = "https://www.x.com/ZerfBarbut"
    instagram = "https://www.instagram.com/zerf_fcb/"
    whatsapp = "https://whatsapp.com/channel/0029VbBBxBa2v1Ik4095g20d"
    
    prompt = f"""
    Actúa como el Community Manager de ZerfAnalitza. Crea la descripción para YouTube.

    CONTENIDO DEL VÍDEO (Transcripción):
    {texto_limpio[:15000]}

    TU TAREA:
    1. Escribe un resumen de 3-4 puntos clave basados ÚNICAMENTE en la transcripción.
    2. Usa emoticonos y un tono barcelonista (culé).
    3. Incluye hashtags relevantes al final.

    ESTRUCTURA DE RESPUESTA OBLIGATORIA (Copia este formato EXACTO):
    [Tu resumen aquí]

    ⎯⎯⎯⎯⎯ APOYA EL CANAL ⎯⎯⎯⎯⎯
    Házte PATREON desde 10 céntimos al día, APOYA el canal y vive el Barça desde nuestro canal de WhatsApp EXCLUSIVO para Patreons 👋
    ▶ {patreon}

    ⎯⎯⎯⎯⎯ SÍGUEME EN REDES ⎯⎯⎯⎯⎯
    🐦 X (Twitter): {twitter}
    📸 Instagram: {instagram}
    💬 Canal WhatsApp: {whatsapp}

    ---
    [Hashtags aquí]

    Força Barça!
    """
    
    print("   [AI] Generando descripción con RRSS...")
    try:
        # Desactivar filtros de seguridad para asegurar que los links no se bloqueen
        safety = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt, safety_settings=safety)
        return response.text.strip()
    except Exception as e:
        print(f"   [ERROR AI] {e}")
        # Retornar al menos un esqueleto si falla la IA
        return f"Resumen del vídeo pendiente...\n\n---\nAPÓYANOS EN PATREON: {patreon}\nTWITTER/X: {twitter}\nINSTAGRAM: {instagram}\n---\n\n#FCBarcelona #Barça\n\nForça Barça!"

# ── SUBIDA A YOUTUBE ──────────────────────────────────────────────────────────
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
                raise FileNotFoundError(f"No se encontró {CLIENT_SECRETS_FILE}. Necesitas crear una app en Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            pickle.dump(creds, token)
            
    return build("youtube", "v3", credentials=creds)

def subir_descripcion_a_youtube(youtube_id: str, description: str):
    """Actualiza la descripción de un vídeo de YouTube."""
    youtube = get_youtube_service()
    
    print(f"   [YT] Actualizando metadatos para {youtube_id}...")
    
    # Obtener el título actual para no perderlo
    video_res = youtube.videos().list(part="snippet", id=youtube_id).execute()
    if not video_res.get('items'):
        raise ValueError(f"No se encontró el vídeo {youtube_id} en YouTube")
    
    snippet = video_res['items'][0]['snippet']
    category_id = snippet.get('categoryId', '17') # Default Deportes si falla
    
    # Actualizar descripción manteniendo el título
    youtube.videos().update(
        part="snippet",
        body={
            "id": youtube_id,
            "snippet": {
                "title": snippet['title'],
                "description": description,
                "categoryId": category_id
            }
        }
    ).execute()
    print(f"   [YT] ✅ Descripción actualizada en YouTube.")

def subir_localizacion_a_youtube(youtube_id: str, language_code: str, title: str, description: str):
    """Añade o actualiza la localización del vídeo en un idioma específico manteniendo el predeterminado."""
    youtube = get_youtube_service()
    
    print(f"   [YT] Añadiendo localización ({language_code}) de título y descripción para {youtube_id}...")
    
    # 1. Obtener la información actual (localizations y snippet default)
    video_res = youtube.videos().list(part="snippet,localizations", id=youtube_id).execute()
    if not video_res.get('items'):
        raise ValueError(f"No se encontró el vídeo {youtube_id} en YouTube")
    
    video = video_res['items'][0]
    
    # Asegurarnos de indicar a YouTube cuál es el idioma predeterminado si no lo tiene
    default_lang = video['snippet'].get('defaultLanguage', 'es')
    if 'defaultLanguage' not in video['snippet']:
         video['snippet']['defaultLanguage'] = default_lang
         
    localizations = video.get('localizations', {})
    
    # 2. Modificar/agregar el idioma al dict localizations
    localizations[language_code] = {
        "title": title[:100],  # Youtube max limit es 100
        "description": description
    }
    
    # 3. Actualizar vídeo completo pasando la parte 'localizations'
    try:
        youtube.videos().update(
            part="snippet,localizations",
            body={
                "id": youtube_id,
                "snippet": video['snippet'],
                "localizations": localizations
            }
        ).execute()
        print(f"   [YT] ✅ Título y descripción en '{language_code}' actualizados en YouTube.")
    except Exception as e:
        print(f"   [ERROR YT] Fallo subiendo localización: {e}")
        raise e

def subir_srt_a_youtube(youtube_id: str, srt_content: str, language_code: str = 'es'):
    """Sube o actualiza un archivo de subtítulos a YouTube."""
    
    language_names = {
        'es': 'Español',
        'en': 'English',
        'pt': 'Português',
        'fr': 'Français',
        'it': 'Italiano',
        'de': 'Deutsch',
        'id': 'Indonesia',
        'ar': 'العربية'
    }
    
    # Format native name, fallback to standard language code if not found
    native_name = language_names.get(language_code, language_code.upper())
    name = f"{native_name} - Zerf Transcript" if language_code == 'es' else native_name
    
    youtube = get_youtube_service()
    
    # 1. Guardar SRT temporalmente
    tmp_file = f"temp_upload_{youtube_id}.srt"
    with open(tmp_file, "w", encoding="utf-8") as f:
        f.write(srt_content)
    
    print(f"   [YT] Gestionando subtítulos ({language_code}) para {youtube_id}...")
    
    try:
        # 2. Comprobar si ya existe y borrar si es necesario
        results = youtube.captions().list(part="snippet", videoId=youtube_id).execute()
        for item in results.get('items', []):
            if item['snippet']['language'] == language_code:
                caption_id = item['id']
                print(f"   [YT] Borrando versión anterior ({caption_id})...")
                youtube.captions().delete(id=caption_id).execute()
        
        # 3. Insertar la nueva versión
        body = {
            'snippet': {
                'videoId': youtube_id,
                'language': language_code,
                'name': name,
                'isDraft': False
            }
        }
        
        media = MediaFileUpload(tmp_file, mimetype='text/plain', resumable=True)
        request = youtube.captions().insert(part="snippet", body=body, media_body=media)
        
        response = request.execute()
        return response
    except Exception as e:
        print(f"   [ERROR YT] {e}")
        raise e
    finally:
        if os.path.exists(tmp_file):
            try: os.remove(tmp_file)
            except: pass

# ── PROCESAMIENTO ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gestor de subtítulos Zerf.")
    parser.add_argument('--video', type=str, required=True, help="YouTube ID del vídeo")
    parser.add_argument('--translate', type=str, help="Código de idioma para traducir (ej: en, fr, ca)")
    parser.add_argument('--refine', action='store_true', help="Refinar el SRT/VTT original (Sp to Sp)")
    parser.add_argument('--upload', action='store_true', help="Subir el SRT actual a YouTube")
    parser.add_argument('--lang', type=str, default='es', help="Idioma para la subida (default: es)")
    
    args = parser.parse_args()
    
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        video = session.query(Video).filter_by(youtube_id=args.video).first()
        if not video:
            print(f"[ERROR] El vídeo {args.video} no está en la base de datos.")
            return

        # Obtener el SRT (en orden: Local VTT si --refine, DB, o Drive)
        srt_content = None
        vtt_path = f"youtube_subs/{args.video}.es.vtt"

        if args.refine and os.path.exists(vtt_path):
            print(f"   [INFO] Refinando desde VTT original: {vtt_path}")
            from src.utils import vtt_to_srt
            with open(vtt_path, 'r', encoding='utf-8') as vf:
                vtt_raw = vf.read()
                srt_content = vtt_to_srt(vtt_raw)
        
        if not srt_content:
            if video.transcription and video.transcription.srt_content:
                srt_content = video.transcription.srt_content
            else:
                # Intentar buscar en Drive
                if os.path.isdir(SRT_DIR):
                    for f in os.listdir(SRT_DIR):
                        if args.video in f:
                            with open(os.path.join(SRT_DIR, f), 'r', encoding='utf-8') as srt_f:
                                srt_content = srt_f.read()
                            break
        
        if not srt_content:
            print(f"[ERROR] No se encontró SRT ni VTT para el vídeo {args.video}")
            return

        # 1. REFINAR (Spanish to Spanish)
        if args.refine:
            try:
                refinado = traducir_srt_gemini(srt_content, "es")
                out_file = f"SRT_es_{args.video}.srt"
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(refinado)
                print(f"   [OK] SRT refinado guardado en: {out_file}")
                srt_content = refinado # Usar para el resto del script
            except Exception as e:
                print(f"[ERROR Refinamiento] {e}")

        # 2. TRADUCIR (Si se pide)
        if args.translate:
            try:
                traduccion = traducir_srt_gemini(srt_content, args.translate)
                out_file = f"SRT_{args.translate}_{args.video}.srt"
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(traduccion)
                print(f"   [OK] Traducción guardada en: {out_file}")
                srt_content = traduccion # Usar la traducción para subir si se pide
                args.lang = args.translate # Cambiar el idioma de subida
            except Exception as e:
                print(f"[ERROR Traducción] {e}")

        # 3. SUBIR (Si se pide, sube lo que haya en srt_content)
        if args.upload:
            try:
                subir_srt_a_youtube(args.video, srt_content, args.lang)
                print(f"   [OK] SRT subido a YouTube correctamente.")
            except Exception as e:
                print(f"[ERROR Subida] {e}")
                if "permissions" in str(e).lower() or "authorized" in str(e).lower():
                    print("\n💡 TIP: El error 403 suele indicar que la cuenta que elegiste en el navegador NO es la dueña del canal.")
                    print("   Prueba a borrar el archivo 'token.pickle' y vuelve a ejecutar el comando para elegir otra cuenta.")

    finally:
        session.close()

if __name__ == "__main__":
    main()
