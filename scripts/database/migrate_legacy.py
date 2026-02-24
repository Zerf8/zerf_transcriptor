# -*- coding: utf-8 -*-
"""
Script de Migración de Transcripciones (Legacy -> Nuevo Formato)
"""

import os
import re
import shutil
import unicodedata
from datetime import datetime
import difflib

# ================= RUTAS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OLD_TXT_DIR = os.path.join(BASE_DIR, "output", "transcripciones", "txt")
OLD_SRT_DIR = os.path.join(BASE_DIR, "output", "transcripciones", "srt")

NEW_BASE_DIR = os.path.join(BASE_DIR, "output", "Transcripts_Video")
NEW_TXT_DIR = os.path.join(NEW_BASE_DIR, "TXT_NotebookLM")
NEW_SRT_DIR = os.path.join(NEW_BASE_DIR, "SRT_YouTube")
NEW_AUDIO_DIR = os.path.join(NEW_BASE_DIR, "AUDIO_MP3")

LISTA_MAESTRA = os.path.join(BASE_DIR, "lista_maestra_videos.txt")

# ================= UTILIDADES =================

def setup_dirs():
    for d in [NEW_TXT_DIR, NEW_SRT_DIR, NEW_AUDIO_DIR]:
        os.makedirs(d, exist_ok=True)

def limpiar_nombre_archivo(texto):
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    texto = re.sub(r'[^\w\s-]', '', texto)
    texto = re.sub(r'[\s]+', '_', texto)
    return texto[:100]

def generar_nombre_nuevo(fecha_str, titulo, video_id):
    tit_limpio = limpiar_nombre_archivo(titulo)
    return f"{fecha_str}_{tit_limpio}_{video_id}"

def extraer_id_url(url):
    try:
        if "v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
    except:
        return None
    return None

def buscar_fichero_antiguo(titulo_buscado, lista_ficheros):
    """
    Busca el fichero más parecido en la lista antigua.
    Devuelve (nombre_fichero, ratio_similitud)
    """
    mejor_match = None
    mejor_ratio = 0.0
    
    # Normalizamos para comparar
    titulo_buscado_norm = limpiar_nombre_archivo(titulo_buscado).lower().replace('_', ' ')
    
    for fichero in lista_ficheros:
        # El fichero antiguo suele ser 'YYYYMMDD TITULO.txt'
        # Quitamos la fecha inicial (8 digitos) si existe
        nombre_sin_ext = os.path.splitext(fichero)[0]
        parts = nombre_sin_ext.split(' ', 1)
        if len(parts) > 1 and parts[0].isdigit() and len(parts[0]) == 8:
            titulo_fichero = parts[1]
        else:
            titulo_fichero = nombre_sin_ext
            
        titulo_fichero_norm = limpiar_nombre_archivo(titulo_fichero).lower().replace('_', ' ')
        
        # OJO: Los archivos antiguos tienen espacios, los nuevos guiones bajos.
        # Comparamos:
        ratio = difflib.SequenceMatcher(None, titulo_buscado_norm, titulo_fichero_norm).ratio()
        
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor_match = fichero

    return mejor_match, mejor_ratio

# ================= MAIN =================

def main():
    print("Iniciando Migracion...")
    setup_dirs()
    
    if not os.path.exists(LISTA_MAESTRA):
        print("No se encuentra lista_maestra_videos.txt")
        return

    # Leer lista maestra
    with open(LISTA_MAESTRA, 'r', encoding='utf-8') as f:
        videos = [l.strip() for l in f if '|' in l]

    # Leer ficheros antiguos disponibles
    if not os.path.exists(OLD_TXT_DIR):
        print("No existe carpeta antigua de TXT. Nada que migrar.")
        return
        
    ficheros_antiguos_txt = os.listdir(OLD_TXT_DIR)
    print(f"Archivos antiguos encontrados: {len(ficheros_antiguos_txt)}")

    migrados = 0
    
    for i, linea in enumerate(videos):
        parts = linea.split('|')
        url = parts[0].strip()
        titulo = parts[1].strip() if len(parts) > 1 else "SinTitulo"
        
        video_id = extraer_id_url(url)
        if not video_id:
            continue
            
        # Intentamos adivinar la fecha del archivo antiguo si existe
        # (Esto es difícil sin metadatos, usaremos la fecha del nombre del archivo antiguo si lo encontramos)
        
        # 1. Buscar correspondencia
        match_txt, ratio = buscar_fichero_antiguo(titulo, ficheros_antiguos_txt)
        
        if match_txt and ratio > 0.6: # Umbral más permisivo (antes 0.85)
            # Tenemos candidato
            path_antiguo_txt = os.path.join(OLD_TXT_DIR, match_txt)
            
            # Extraer fecha del nombre antiguo
            fecha = "20240101" # Default
            parts = match_txt.split(' ', 1)
            if parts[0].isdigit() and len(parts[0]) == 8:
                fecha = parts[0]
            
            # Generar nombre nuevo ESTRICTO
            nuevo_nombre_base = generar_nombre_nuevo(fecha, titulo, video_id)
            
            path_nuevo_txt = os.path.join(NEW_TXT_DIR, nuevo_nombre_base + ".txt")
            path_nuevo_srt = os.path.join(NEW_SRT_DIR, nuevo_nombre_base + ".srt")
            path_nuevo_audio = os.path.join(NEW_AUDIO_DIR, nuevo_nombre_base + ".mp3")
            
            # SRT Antiguo (asumimos mismo nombre base pero .srt)
            nombre_base_antiguo = os.path.splitext(match_txt)[0]
            path_antiguo_srt = os.path.join(OLD_SRT_DIR, nombre_base_antiguo + ".srt")
            
            if os.path.exists(path_nuevo_txt):
                print(f"Ya migrado: {titulo[:30]}...")
                continue
                
            print(f"Migrando: {match_txt} \n      -> {nuevo_nombre_base}")
            
            # Copiar TXT
            shutil.copy2(path_antiguo_txt, path_nuevo_txt)
            
            # Copiar SRT si existe
            if os.path.exists(path_antiguo_srt):
                shutil.copy2(path_antiguo_srt, path_nuevo_srt)
            else:
                print("   No se encontro SRT antiguo")
                
            migrados += 1
        else:
            # print(f"   No encontrado en backup: {titulo[:30]}... (Ratio: {ratio:.2f})")
            pass

    print(f"\nMigracion completada. {migrados} videos recuperados al nuevo formato.")
    print("Ahora puedes ejecutar el script de transcripción y saltará estos videos.")

if __name__ == "__main__":
    main()
