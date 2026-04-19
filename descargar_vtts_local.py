"""
descargar_vtts_local.py
========================
Ejecutar desde TU MÁQUINA LOCAL (no en el servidor).

Requisitos:
    pip install yt-dlp pymysql

Uso:
    python3 descargar_vtts_local.py

Qué hace:
    1. Conecta a la base de datos remota y busca vídeos sin VTT.
    2. Descarga los subtítulos automáticos de YouTube usando las cookies
       de tu Chrome local (no necesita exportar nada a mano).
    3. Guarda el contenido VTT directamente en la base de datos.
"""

import subprocess
import sys
import tempfile
import os
import time
import pymysql

# ─── CONFIGURACIÓN DE BASE DE DATOS ──────────────────────────────────────────
DB_HOST = "193.203.168.198"
DB_NAME = "u214755203_zerffcb"
DB_USER = "u214755203_ss"
DB_PASS = "Sreg8888!!88hdb"
DB_PORT = 3306

# Navegador del que leer las cookies automáticamente.
# Opciones: "chrome", "firefox", "edge", "safari", "brave", "chromium"
BROWSER = "chrome"
# ─────────────────────────────────────────────────────────────────────────────


def get_missing_videos(connection):
    """Obtiene los vídeos que no tienen VTT en la base de datos."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT v.id, v.youtube_id, v.title
            FROM videos v
            LEFT JOIN transcriptions t ON v.id = t.video_id
            WHERE t.id IS NULL OR t.vtt IS NULL OR TRIM(t.vtt) = ''
            ORDER BY v.upload_date DESC
        """)
        return cursor.fetchall()


def download_vtt(youtube_id):
    """Descarga el VTT usando las cookies del navegador local."""
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, f"{youtube_id}.%(ext)s")
    expected_file = os.path.join(tmp_dir, f"{youtube_id}.es.vtt")

    command = [
        sys.executable, "-m", "yt_dlp",
        "--cookies-from-browser", BROWSER,
        "--write-auto-subs",
        "--skip-download",
        "--sub-langs", "es",
        "--sub-format", "vtt",
        "-o", output_template,
        "--quiet",
        url
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if os.path.exists(expected_file):
            with open(expected_file, "r", encoding="utf-8") as f:
                content = f.read()
            os.remove(expected_file)
            return content
        else:
            if result.returncode != 0:
                print(f"      ⚠️  Error yt-dlp: {result.stderr.strip()[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"      ⚠️  Timeout al descargar {youtube_id}")
        return None
    except Exception as e:
        print(f"      ⚠️  Excepción: {e}")
        return None


def save_vtt_to_db(connection, video_id, vtt_content):
    """Guarda o actualiza el VTT en la base de datos."""
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO transcriptions (video_id, vtt, language)
            VALUES (%s, %s, 'es')
            ON DUPLICATE KEY UPDATE vtt = VALUES(vtt)
        """, (video_id, vtt_content))
    connection.commit()


def main():
    print("=" * 60)
    print("  Descargador de VTTs → Base de Datos Remota")
    print("=" * 60)
    print(f"\n🌐 Conectando a la base de datos ({DB_HOST})...")

    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT,
            cursorclass=pymysql.cursors.DictCursor
        )
        print("✅ Conexión establecida.\n")
    except Exception as e:
        print(f"❌ No se pudo conectar a la base de datos: {e}")
        sys.exit(1)

    videos = get_missing_videos(connection)

    if not videos:
        print("🎉 ¡No hay vídeos sin VTT! Todo está al día.")
        connection.close()
        return

    total = len(videos)
    print(f"📋 Encontrados {total} vídeos sin VTT. Iniciando descarga...\n")

    ok = 0
    fail = 0

    for idx, video in enumerate(videos, 1):
        yt_id = video["youtube_id"]
        title = video["title"][:50] if video["title"] else "Sin título"
        print(f"[{idx}/{total}] {title}")
        print(f"         https://youtu.be/{yt_id}")

        vtt = download_vtt(yt_id)

        if vtt:
            save_vtt_to_db(connection, video["id"], vtt)
            print(f"      ✅ Guardado en DB ({len(vtt)} caracteres)\n")
            ok += 1
        else:
            print(f"      ❌ Sin subtítulos en español disponibles\n")
            fail += 1

        # Pausa entre descargas para no saturar YouTube
        if idx < total:
            time.sleep(2)

    connection.close()

    print("=" * 60)
    print(f"  PROCESO FINALIZADO")
    print(f"  ✅ Guardados: {ok} VTTs")
    print(f"  ❌ Fallidos:  {fail} vídeos")
    print("=" * 60)


if __name__ == "__main__":
    main()
