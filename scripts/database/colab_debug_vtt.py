# ========================================================
# VERSIÓN 2: CON DEPÓSITO DE ERRORES REVELADOS
# ========================================================
from google.colab import drive
import os
import subprocess

drive.mount('/content/drive')
output_folder = "/content/drive/MyDrive/youtube_missing_vtt"
os.makedirs(output_folder, exist_ok=True)

!pip install -q -U yt-dlp

missing_videos = [
    '-8XfSDss_-w', '02RmfIkWvq4', '29-1HRq0HcQ', '2h_I0YHt0Pg', '33Pq1F8uT6g', 
    '3bU8JzTuEXA', '4AOLx3UMYH8', '4yWqcXV5k2Y', '6fGrzXVt0Ak', '7a93bYVUTxo', 
    'b091fR8ab7A', 'CimIYkohBwQ', 'd4OOgEBEszI', 'd6BMt_QbclU', 'eUsDuZuu8x0', 
    'EXrDBJkmXCU', 'FeM17nvo2Mo', 'FN92I3b49jA', 'GORJPO48YzU', 'KNcxsTtgGAU', 
    'lu1EP-y0ddM', 'LZBGLL6UX5Y', 'M5s2gaD5kxY', 'mKMQKgAN2bE', 'QjJMPk3jNTo', 
    'QR2d0GAsuxI', 'SNCOOwijRL4', 'TduYJif69Ik', 'VAB4VSxr6jU', 'vrUH6L3UlBI', 
    'y_egYgymJAM', 'yZzu3eEndcE', 'zgG9NOpFfpg', 'zsOBTcAL6b4', 'zwXtRmjudd8'
]

# Vamos a atrapar solo el primer video para diagnosticar qué pasa exactamente
test_id = missing_videos[0]

print(f"Probando en profundidad con el ID: {test_id}...")
url = f"https://www.youtube.com/watch?v={test_id}"
output_template = f"{output_folder}/{test_id}.%(ext)s"

# Ejecutamos comando sin esconder nada para que Colab nos enseñe la verdad
!yt-dlp --write-auto-subs --skip-download --sub-langs "es" --sub-format "vtt" -o "{output_template}" "{url}"

print("\n--- TEST FINALIZADO ---")
