#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
TRANSCRIPTOR ZERF - VERSIÓN RESTAURADA Y FIABLE
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════
# INSTALAR DEPENDENCIAS
# ═══════════════════════════════════════════════════════════════════════════

print("📦 Instalando dependencias...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", 
                      "faster-whisper", "yt-dlp"])

from faster_whisper import WhisperModel
import yt_dlp
import gc
from google.colab import drive

print("✅ Dependencias instaladas\n")

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════

LIMITE_VIDEOS = 10  # Prueba inicial de 10 vídeos

# Cambiado a large-v2 para evitar las alucinaciones de la v3 en español
MODELO = "large-v2"

# Rutas Google Drive
DRIVE_BASE = "/content/drive/MyDrive/Transcripts_Barca"
FOLDER_TXT = os.path.join(DRIVE_BASE, "TXT_NotebookLM")
FOLDER_SRT = os.path.join(DRIVE_BASE, "SRT_YouTube")
FOLDER_AUDIO = os.path.join(DRIVE_BASE, "AUDIO_MP3")
LISTA_MAESTRA = os.path.join(DRIVE_BASE, "lista_maestra_videos.txt")

# ═══════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════════

def limpiar_nombre_archivo(texto):
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    texto = re.sub(r'[^\w\s-]', '', texto)
    texto = re.sub(r'[\s]+', '_', texto)
    return texto[:100]

def extraer_fecha_video(info):
    try:
        fecha = info.get('upload_date', '')
        if fecha and len(fecha) == 8:
            return fecha
        return datetime.now().strftime('%Y%m%d')
    except:
        return datetime.now().strftime('%Y%m%d')

# ═══════════════════════════════════════════════════════════════════════════
# PROMPT CONTEXTUAL ORIGINAL
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_BASE = """Transcripción de vídeo de análisis del FC Barcelona narrado por Zerf en español de España.
JUGADORES FC BARCELONA: Lamine Yamal, Marcus Rashford, Fermín López, Ferran Torres, Robert Lewandowski, Marc Casadó, Alejandro Balde, Frenkie de Jong, Iñaki Peña, Eric García, Dani Olmo, Gavi, Pedri, Raphinha, Marc-André ter Stegen, Ronald Araújo, Jules Koundé, Pau Cubarsí, Gerard Martín, Marc Bernal, Ansu Fati, Pellegrino Matarazzo."""

# ═══════════════════════════════════════════════════════════════════════════
# DICCIONARIO DE CORRECCIONES ORIGINAL
# ═══════════════════════════════════════════════════════════════════════════

CORRECCIONES = {
    r"LA\s+MIN\s+YAMA": "Lamine Yamal",
    r"la\s+min\s+yama": "Lamine Yamal",
    r"LA\s+MIN,\s+YAMA": "Lamine Yamal",
    r"LA\s+MIÑA\s+MAL": "Lamine Yamal",
    r"la\s+miña\s+mal": "Lamine Yamal",
    r"\bla\s+min(?:ya)?ma\b": "Lamine Yamal",
    r"\b[Ll]amin\s+[Jj]amal\b": "Lamine Yamal",
    r"\bminyama\b": "Lamine Yamal",
    r"\bLAMIN\b": "Lamine",
    r"\bESTELAMIN\b": "este Lamine",
    r"\bValde\b": "Balde",
    r"\b[Rr]ushford\b": "Rashford",
    r"\braspo\b": "Rashford",
    r"\b[Ll]eandros?(?:qui)?\b": "Lewandowski",
    r"\bbandoski\b": "Lewandowski",
    r"\bFerm[ií]n\b": "Fermín",
    r"\bFerran\b": "Ferran",
    r"\bI[ñn]aki\s+Pe[ñn]a\b": "Iñaki Peña",
    r"\b[Ff]rankie\s+de\s+[Jj]h?on\b": "Frenkie de Jong",
    r"\bCasad[oó]\b": "Casadó",
    r"\bEric\s+Garc[ií]a\b": "Eric García",
    r"\bGUARCÍ\b": "García",
    r"\bDani(?:el)?\s+Olmo\b": "Dani Olmo",
    r"\bRaphinha\b": "Raphinha",
    r"\bRafinha\b": "Raphinha",
    r"\bGavi\b": "Gavi",
    r"\bGabi\b": "Gavi",
    r"\bPedri\b": "Pedri",
    r"\bAra[uú]jo\b": "Araújo",
    r"\bKound[ée]\b": "Koundé",
    r"\bCund[ée]s?\b": "Koundé",
    r"\bCubar(?:s[ií])\b": "Cubarsí",
    r"\bBar[çc]a\b": "Barça",
    r"\bATLEO\s+MADRID\b": "Atlético Madrid",
    r"\bEL\s+CHISO\b": "el Elche",
    r"\b[Mm]onjic\b": "Montjuïc",
    r"\bCamp\s+Nou\b": "Camp Nou",
    r"\bBar\s+Canaletes\b": "Bar Canaletes",
    r"\bPITAL\s+LA\s+ANGUILA\b": "Peter La Anguila",
    r"\bcul[ée](?:s)?\b": "culés",
    r"\bZerfistas?\b": "Zerfistas",
    r"\bFor[çc]a\s+Bar[çc]a\b": "Força Barça",
    r"¡¡¡GRACIAS\s+POR\s+VER!!!": "",
}

def corregir_transcripcion(texto):
    for patron, reemplazo in CORRECCIONES.items():
        texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def format_timestamp_srt(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generar_srt(segments, output_path):
    with open(output_path, 'w', encoding='utf-8', errors='ignore') as f:
        for i, segment in enumerate(segments, 1):
            start = format_timestamp_srt(segment.start)
            end = format_timestamp_srt(segment.end)
            texto = corregir_transcripcion(segment.text.strip())
            f.write(f"{i}\n{start} --> {end}\n{texto}\n\n")

# ═══════════════════════════════════════════════════════════════════════════
# PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════════════════

print("\n📁 Montando Drive...")
drive.mount('/content/drive', force_remount=True)

for f in [FOLDER_TXT, FOLDER_SRT, FOLDER_AUDIO]:
    os.makedirs(f, exist_ok=True)

print(f"\n⏳ Cargando Faster-Whisper '{MODELO}'...")
device = "cuda" if torch.cuda.is_available() else "cpu"
model = WhisperModel(MODELO, device=device, compute_type="float16" if device == "cuda" else "int8")

if not os.path.exists(LISTA_MAESTRA):
    print(f"❌ No encontrado: {LISTA_MAESTRA}")
    exit()

with open(LISTA_MAESTRA, 'r', encoding='utf-8') as f:
    lineas = [l.strip() for l in f.readlines() if "|" in l]

lineas_proceso = lineas[:LIMITE_VIDEOS] if LIMITE_VIDEOS > 0 else lineas

for i, linea in enumerate(lineas_proceso, 1):
    try:
        url, titulo = linea.split("|", 1)
        url, titulo = url.strip(), titulo.strip()
        
        print(f"\n🎬 [{i}/{len(lineas_proceso)}] {titulo[:50]}...")
        
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            fecha = extraer_fecha_video(info)
            video_titulo_yt = info.get('title', titulo)
            
        nombre_base = f"{fecha}_{limpiar_nombre_archivo(video_titulo_yt)}"
        audio_path = os.path.join(FOLDER_AUDIO, f"{nombre_base}.mp3")
        srt_path = os.path.join(FOLDER_SRT, f"{nombre_base}.srt")
        txt_path = os.path.join(FOLDER_TXT, f"{nombre_base}.txt")
        
        if not os.path.exists(audio_path):
            print("   ⬇️ Descargando audio...")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_path.replace('.mp3', ''),
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        print("   🎤 Transcribiendo...")
        segments, _ = model.transcribe(
            audio_path,
            language="es",
            initial_prompt=PROMPT_BASE,
            beam_size=5,
            condition_on_previous_text=False, # Anti-bucles
            vad_filter=False                 # Sin cortes de inicio
        )
        
        segments_list = list(segments)
        generar_srt(segments_list, srt_path)
        
        texto_completo = " ".join([seg.text for seg in segments_list])
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"TÍTULO: {video_titulo_yt}\n\n{corregir_transcripcion(texto_completo)}")
        
        print(f"   💾 Guardado: {nombre_base}")
        gc.collect()

    except Exception as e:
        print(f"   ❌ ERROR: {e}")

print("\n✅ PROCESO COMPLETADO")
