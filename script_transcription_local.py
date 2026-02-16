# -*- coding: utf-8 -*-
"""
Script de Transcripción Local (Zerfpino Edition)
Adaptado para: AMD Ryzen 9 3900X + NVIDIA GTX 1660 SUPER

Este script replica la lógica "Winner" del notebook de Colab pero optimizado para ejecución local.
"""

import os
import sys
import subprocess
import whisper
import yt_dlp
import re
import unicodedata
import gc
import torch
from datetime import datetime

# ==========================================
# CONFIGURACIÓN LOCAL
# ==========================================

# Rutas Base (Usamos rutas relativas al script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_BASE = os.path.join(BASE_DIR, "output", "Transcripts_Video")

# Configuración de FFmpeg local (si existe en la carpeta del proyecto)
LOCAL_FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")
if os.path.exists(LOCAL_FFMPEG_PATH):
    print(f"🔧 FFmpeg local detectado: {LOCAL_FFMPEG_PATH}")
    os.environ["PATH"] += os.pathsep + BASE_DIR
else:
    print("⚠️ FFmpeg local no encontrado en la raíz. Asegúrate de que FFmpeg esté en el PATH del sistema.")

# Carpetas de salida
FOLDER_SRT = os.path.join(OUTPUT_BASE, "SRT_YouTube")
FOLDER_TXT = os.path.join(OUTPUT_BASE, "TXT_NotebookLM")
FOLDER_AUDIO = os.path.join(OUTPUT_BASE, "AUDIO_MP3")
LISTA_MAESTRA = os.path.join(BASE_DIR, "lista_maestra_videos.txt")

# Configuración de Transcripción
MODEL_SIZE = "large"
NUM_VIDEOS_LIMIT = 1  # Por defecto 5, puedes cambiarlo aquí o poner 0 para todos

# Contexto para el modelo
INITIAL_PROMPT = "Transcripción de análisis del FC Barcelona. Jugadores: Lamine Yamal, Lewandowski, Cubarsí, Fermín, Gavi, Pedri, Araújo, Koundé, Raphinha, Ter Stegen, Pau Víctor, Dani Olmo, Flick."

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def setup_directories():
    """Crea las carpetas necesarias si no existen."""
    for f in [FOLDER_SRT, FOLDER_TXT, FOLDER_AUDIO]:
        os.makedirs(f, exist_ok=True)
        print(f"📁 Directorio verificado: {f}")

def extraer_id_url(url):
    """Intenta extraer el ID de video de una URL de YouTube"""
    try:
        if "v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
    except:
        return None
    return None

def limpiar_nombre_archivo(texto):
    """Limpia el título para evitar problemas en sistemas de archivos Windows"""
    # Normalizar caracteres unicode
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    # Permitir solo letras, números, guiones y espacios
    texto = re.sub(r'[^\w\s-]', '', texto)
    # Reemplazar espacios múltiples por guion bajo
    texto = re.sub(r'[\s]+', '_', texto)
    return texto[:100]  # Limitar longitud para evitar errores de ruta larga en Windows

def generar_nombre_final(info):
    """Genera el nombre estricto: YYMMDD_TITULO_ID"""
    fecha = info.get('upload_date', datetime.now().strftime('%Y%m%d'))
    titulo = info.get('title', 'Video_Sin_Titulo')
    video_id = info.get('id', 'UnknownID')
    
    titulo_limpio = limpiar_nombre_archivo(titulo)
    return f"{fecha}_{titulo_limpio}_{video_id}"

def format_timestamp(seconds):
    """Formato SRT estándar: 00:00:00,000"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def write_srt(segments, path):
    """Escribe el archivo SRT desde los segmentos de OpenAI Whisper"""
    with open(path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments, 1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text'].strip()
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

# ==========================================
# PROCESO PRINCIPAL
# ==========================================

def main():
    print(f"🚀 Iniciando Transcriptor Zerf (Local Edition)")
    print(f"💻 Sistema: Windows - Zerfpino")
    
    # 1. Verificar GPU
    if torch.cuda.is_available():
        print(f"✅ GPU Detectada: {torch.cuda.get_device_name(0)}")
        device = "cuda"
    else:
        print("⚠️ PRECAUCIÓN: GPU no detectada. Se usará CPU (será lento).")
        device = "cpu"

    setup_directories()

    # 2. Cargar Modelo
    print(f"⏳ Cargando modelo Whisper '{MODEL_SIZE}' en {device}...")
    try:
        model = whisper.load_model(MODEL_SIZE, device=device)
        print("🤖 Modelo cargado correctamente.")
    except Exception as e:
        print(f"❌ Error cargando el modelo: {e}")
        print("Intenta instalar dependencias: pip install git+https://github.com/openai/whisper.git")
        return

    # 3. Leer lista de videos
    if not os.path.exists(LISTA_MAESTRA):
        print(f"❌ ERROR: No se encuentra {LISTA_MAESTRA}")
        print("Crea este archivo en la carpeta del script con las URLs de los videos.")
        return

    with open(LISTA_MAESTRA, 'r', encoding='utf-8') as f:
        all_videos = [line.strip() for line in f if '|' in line and not line.startswith('#')]

    print(f"📋 Encontrados {len(all_videos)} videos en la lista maestra.")
    
    videos_procesados_count = 0
    
    for i, line_raw in enumerate(all_videos, 1):
        # Chequeo de seguridad del límite
        if NUM_VIDEOS_LIMIT > 0 and videos_procesados_count >= NUM_VIDEOS_LIMIT:
            print(f"🛑 Se ha alcanzado el límite de {NUM_VIDEOS_LIMIT} videos procesados.")
            break

        try:
            # Parsear línea
            parts = line_raw.split('|')
            url = parts[0].strip()
            title_hint = parts[1].strip() if len(parts) > 1 else ""
            desc_hint = parts[2].strip() if len(parts) > 2 else ""
            
            # Prompt enriquecido
            current_prompt = f"{title_hint}. {desc_hint[:200]}. {INITIAL_PROMPT}"
            
            print(f"\n🎬 Procesando [{i}/{len(all_videos)}]: {url}")
            
            # Verificación rápida por ID
            video_id_rapido = extraer_id_url(url)
            if video_id_rapido:
                ya_existe_srt = any(f.endswith(f"_{video_id_rapido}.srt") for f in os.listdir(FOLDER_SRT))
                ya_existe_txt = any(f.endswith(f"_{video_id_rapido}.txt") for f in os.listdir(FOLDER_TXT))
                
                if ya_existe_srt and ya_existe_txt:
                    print(f"   🚀 Video {video_id_rapido} ya procesado. Saltando...")
                    continue

            # Configurar yt-dlp
            ydl_opts_info = {
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': BASE_DIR if os.path.exists(LOCAL_FFMPEG_PATH) else None
            }
            
            # Obtener metadatos
            try:
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as e:
                print(f"   ⚠️ Error obteniendo info del video: {e}")
                continue

            nombre_final = generar_nombre_final(info)
            audio_path = os.path.join(FOLDER_AUDIO, f"{nombre_final}.mp3")
            srt_path = os.path.join(FOLDER_SRT, f"{nombre_final}.srt")
            txt_path = os.path.join(FOLDER_TXT, f"{nombre_final}.txt")

            print(f"   🏷️ Nombre: {nombre_final}")

            # Descargar audio
            if not os.path.exists(audio_path):
                print("   ⬇️ Descargando audio (MP3)...")
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': audio_path.replace('.mp3', ''),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'quiet': True,
                    'no_warnings': True,
                    'ffmpeg_location': BASE_DIR if os.path.exists(LOCAL_FFMPEG_PATH) else None
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            else:
                print("   ✅ Audio existente.")

            # Transcribir
            print("   🎤 Transcribiendo (Whisper Large)... esto tomará unos minutos...")
            result = model.transcribe(
                audio_path, 
                language="es", 
                initial_prompt=current_prompt,
                verbose=False
            )

            # Guardar resultados
            write_srt(result['segments'], srt_path)
            print(f"   💾 SRT: {os.path.basename(srt_path)}")

            texto_completo = result['text'].strip()
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(f"VIDEO: {info.get('title')}\nURL: {url}\n\n{texto_completo}")
            print(f"   💾 TXT: {os.path.basename(txt_path)}")
            
            videos_procesados_count += 1
            
            # Limpieza GPU
            gc.collect()
            torch.cuda.empty_cache()

        except Exception as e:
            print(f"   ❌ ERROR CRÍTICO procesando {url}: {str(e)}")
            import traceback
            traceback.print_exc()

    print("\n🎉 ¡PROCESO COMPLETADO!")

if __name__ == "__main__":
    main()
