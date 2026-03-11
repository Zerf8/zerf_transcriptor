"""
Este script es una versión simplificada diseñada para ejecutarse en Google Colab.
Contiene una lista dura (hardcoded) de 35 IDs de videos de YouTube a los que les 
falta el archivo VTT, y utiliza yt-dlp para descargarlos directamente a Google Drive.
"""
# ========================================================
# COPIA Y PEGA ESTE BLOQUE EN UNA CELDA DE GOOGLE COLAB
# Y PRESIONA EL BOTÓN DE "PLAY" (O SHIFT + ENTER)
# ========================================================

# 1. Montamos tu Google Drive
from google.colab import drive
drive.mount('/content/drive')

import os
import subprocess

# 2. Carpeta de destino (se creará una en el inicio de tu Drive)
output_folder = "/content/drive/MyDrive/youtube_missing_vtt"
os.makedirs(output_folder, exist_ok=True)

# 3. Instalamos silenciosamente yt-dlp
!pip install -q -U yt-dlp

# 4. Los 35 IDs que faltan en tu BD Hostinger
missing_videos = [
    '-8XfSDss_-w', '02RmfIkWvq4', '29-1HRq0HcQ', '2h_I0YHt0Pg', '33Pq1F8uT6g', 
    '3bU8JzTuEXA', '4AOLx3UMYH8', '4yWqcXV5k2Y', '6fGrzXVt0Ak', '7a93bYVUTxo', 
    'b091fR8ab7A', 'CimIYkohBwQ', 'd4OOgEBEszI', 'd6BMt_QbclU', 'eUsDuZuu8x0', 
    'EXrDBJkmXCU', 'FeM17nvo2Mo', 'FN92I3b49jA', 'GORJPO48YzU', 'KNcxsTtgGAU', 
    'lu1EP-y0ddM', 'LZBGLL6UX5Y', 'M5s2gaD5kxY', 'mKMQKgAN2bE', 'QjJMPk3jNTo', 
    'QR2d0GAsuxI', 'SNCOOwijRL4', 'TduYJif69Ik', 'VAB4VSxr6jU', 'vrUH6L3UlBI', 
    'y_egYgymJAM', 'yZzu3eEndcE', 'zgG9NOpFfpg', 'zsOBTcAL6b4', 'zwXtRmjudd8'
]

# 5. Iteramos y descargamos directamente hacia el Google Drive montado
for i, yt_id in enumerate(missing_videos, 1):
    print(f"[{i}/{len(missing_videos)}] Descargando {yt_id}...")
    url = f"https://www.youtube.com/watch?v={yt_id}"
    output_template = f"{output_folder}/{yt_id}.%(ext)s"
    
    command = [
        "yt-dlp",
        "--write-auto-subs",
        "--skip-download",
        "--sub-langs", "es",
        "--sub-format", "vtt",
        "-o", output_template,
        url
    ]
    
    subprocess.run(command)

print(f"\n✅ Proceso Finalizado. Ve a tu Google Drive a por los VTT dentro de la carpeta 'youtube_missing_vtt'.")
