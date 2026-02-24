# ========================================================
# SCRIPT FINAL COLAB: DESCARGA CON COOKIES ANTI-BOT
# ========================================================

# 1. Montamos tu Google Drive
from google.colab import drive
import os
import subprocess

drive.mount('/content/drive')
output_folder = "/content/drive/MyDrive/youtube_missing_vtt"
os.makedirs(output_folder, exist_ok=True)

# 2. Instalamos yt-dlp y NodeJS (para el reto Anti-Bot)
print("Instalando dependencias (yt-dlp y NodeJS)...")
!pip install -q -U yt-dlp
!apt-get install -y nodejs > /dev/null

# 3. Subida manual de Cookies
from google.colab import files
print("\n🔥 ATENCIÓN: Sube aquí tu archivo 'cookies.txt'. Dale al botón 'Elegir archivos' debajo:")
uploaded = files.upload()

cookie_file = list(uploaded.keys())[0] if uploaded else None

if not cookie_file:
    print("❌ ERROR: No subiste ningún archivo cookies.txt. Cancelo el proceso.")
else:
    print(f"✅ Cookies cargadas: {cookie_file}")
    
    missing_videos = [
        '-8XfSDss_-w', '02RmfIkWvq4', '29-1HRq0HcQ', '2h_I0YHt0Pg', '33Pq1F8uT6g', 
        '3bU8JzTuEXA', '4AOLx3UMYH8', '4yWqcXV5k2Y', '6fGrzXVt0Ak', '7a93bYVUTxo', 
        'b091fR8ab7A', 'CimIYkohBwQ', 'd4OOgEBEszI', 'd6BMt_QbclU', 'eUsDuZuu8x0', 
        'EXrDBJkmXCU', 'FeM17nvo2Mo', 'FN92I3b49jA', 'GORJPO48YzU', 'KNcxsTtgGAU', 
        'lu1EP-y0ddM', 'LZBGLL6UX5Y', 'M5s2gaD5kxY', 'mKMQKgAN2bE', 'QjJMPk3jNTo', 
        'QR2d0GAsuxI', 'SNCOOwijRL4', 'TduYJif69Ik', 'VAB4VSxr6jU', 'vrUH6L3UlBI', 
        'y_egYgymJAM', 'yZzu3eEndcE', 'zgG9NOpFfpg', 'zsOBTcAL6b4', 'zwXtRmjudd8'
    ]

    print("\nIniciando descargas seguras...\n")
    for i, yt_id in enumerate(missing_videos, 1):
        print(f"[{i}/{len(missing_videos)}] Procesando {yt_id}...")
        url = f"https://www.youtube.com/watch?v={yt_id}"
        output_template = f"{output_folder}/{yt_id}.%(ext)s"
        
        command = [
            "yt-dlp",
            "--cookies", cookie_file,           # Usando tus cookies
            "--js-runtimes", "node",            # Furia Anti-Bot
            "--remote-components", "ejs:github",
            "--write-auto-subs",
            "--skip-download",
            "--sub-langs", "es",
            "--sub-format", "vtt",
            "-o", output_template,
            url
        ]
        
        # Ejecutamos ocultando los warning inútiles para no manchar
        res = subprocess.run(command, capture_output=True, text=True)
        
        if res.returncode != 0:
            if "Requested format is not available" in res.stderr:
                print(f"   ⚠️ VTT no disponible en YouTube para el ID {yt_id}.")
            else:
                print(f"   ❌ Error desconocido con {yt_id}. Revisa log:\n{res.stderr[:200]}")
        else:
            print(f"   ✅ VTT Descargado con éxito para {yt_id}.")

    print(f"\n🚀 Proceso FINALIZADO. Revisa la carpeta 'youtube_missing_vtt' en tu Drive.")
