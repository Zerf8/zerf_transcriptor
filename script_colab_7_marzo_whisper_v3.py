# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║ ZERF TRANSCRIPTOR - MOTOR DEFINITIVO COLAB V3.1          ║
║ Túnel SSH + Drive (Fallback yt-dlp) + Stable-TS (GPU)    ║
╚══════════════════════════════════════════════════════════╝
"""
import os, json, time, re, requests, gc
import torch
import stable_whisper
import yt_dlp
from sshtunnel import SSHTunnelForwarder
import pymysql
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from google.colab import drive

# ── 1. CONFIGURACIÓN ────────────────────────────────────────
LIMIT_VIDEOS = 1  # Forzado a 1 para pruebas iniciales

SSH_HOST = '46.202.172.197'
SSH_PORT = 65002
SSH_USER = 'u214755203'
SSH_PASS = '/5z*TB7jdMWynV+'

DB_USER = 'u214755203_ss'
DB_PASS = 'Sreg8888!!88hdb'
DB_NAME = 'u214755203_zerffcb'

PROMPT_BASE = (
    "Transcripción en español y català. Hola Culerada y Hola Zerfistas. "
    "Análisis del FC Barcelona. Canal: Zerf. Comunidad: Zerfistas. Culerada. "
    "Evitar repeticiones y alucinaciones. Si hay silencio, no inventar palabras. "
)

FOLDER_AUDIO = "/content/drive/MyDrive/Transcripts_Barca/AUDIO_MP3"

# ── 2. PLANTILLAS E INICIALIZACIÓN ──────────────────────────
PLANTILLAS_POR_ANO = {
    2016: "Ter Stegen, Bravo, Piqué, Mascherano, Mathieu, Digne, Jordi Alba, Aleix Vidal, Busquets, Iniesta, Rakitić, Rafinha Alcântara, Arda Turan, Denis Suárez, Messi, Suárez, Neymar, Munir",
    2017: "Ter Stegen, Piqué, Umtiti, Mascherano, Jordi Alba, Semedo, Busquets, Iniesta, Rakitić, André Gomes, Denis Suárez, Paulinho, Messi, Suárez, Dembélé, Deulofeu",
    2018: "Ter Stegen, Piqué, Lenglet, Umtiti, Jordi Alba, Semedo, Busquets, Iniesta, Rakitić, Arthur, Coutinho, Messi, Suárez, Dembélé, Malcom, Munir",
    2019: "Ter Stegen, Piqué, Lenglet, Umtiti, Jordi Alba, Semedo, Busquets, de Jong, Rakitić, Vidal, Arthur, Griezmann, Suárez, Messi, Dembélé, Coutinho, Junior Firpo",
    2020: "Ter Stegen, Piqué, Lenglet, Araujo, Jordi Alba, Dest, Busquets, de Jong, Pedri, Trincão, Mingueza, Griezmann, Messi, Dembélé, Coutinho, Braithwaite",
    2021: "Ter Stegen, Piqué, Araujo, Mingueza, Eric García, Dest, Jordi Alba, Busquets, de Jong, Pedri, Gavi, Luuk de Jong, Kun Agüero, Depay, Ansu Fati, Dembélé, Braithwaite, Coutinho",
    2022: "Ter Stegen, Piqué, Araujo, Koundé, Christensen, Balde, Jordi Alba, Azpilicueta, Marcos Alonso, Busquets, de Jong, Pedri, Gavi, Lewandowski, Raphinha, Ansu Fati, Ferran Torres, Depay, Aubameyang, Dembélé",
    2023: "Ter Stegen, Araujo, Koundé, Christensen, Eric García, Balde, Cancelo, Busquets, de Jong, Pedri, Gavi, Gündoğan, Fermín, Lewandowski, Raphinha, Ansu Fati, Ferran Torres, Dembélé, João Félix, Vitor Roque, Oriol Romeu",
    2024: "Ter Stegen, Iñaki Peña, Araujo, Koundé, Cubarsí, Eric García, Balde, Héctor Fort, Casadó, de Jong, Pedri, Gavi, Fermín, Dani Olmo, Lamine Yamal, Raphinha, Lewandowski, Pau Víctor, Ansu Fati, Flick, Hansi Flick, Laporta, Deco",
    2025: "Ter Stegen, Iñaki Peña, Araujo, Koundé, Cubarsí, Christensen, Balde, Héctor Fort, Álvaro Carreras, Casadó, de Jong, Pedri, Gavi, Fermín, Dani Olmo, Lamine Yamal, Marc Bernal, Raphinha, Lewandowski, Pau Víctor, Ansu Fati, Flick, Hansi Flick, Laporta, Deco"
}

def get_prompt_for_year(date_str: str) -> str:
    try:
        year = int(date_str[:4]) if date_str else 2024
    except:
        year = 2024
    available = sorted(PLANTILLAS_POR_ANO.keys())
    best = available[0]
    for y in available:
        if y <= year: best = y
    return PROMPT_BASE + f"Jugadores de la temporada {best}: {PLANTILLAS_POR_ANO[best]}."

def apply_dictionary_to_srt(srt_path, diccionario):
    if not diccionario: return
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    correcciones = {}
    if "nombres_propios" in diccionario:
        for correcto, variaciones in diccionario["nombres_propios"].items():
            if isinstance(variaciones, list):
                for v in variaciones:
                    if v.strip() and v != correcto: correcciones[v] = correcto

    if "correcciones_aprendidas" in diccionario:
        for mal, bien in diccionario["correcciones_aprendidas"].items():
            correcciones[mal] = bien

    sorted_keys = sorted(correcciones.keys(), key=len, reverse=True)
    for mala_palabra in sorted_keys:
        buena_palabra = correcciones[mala_palabra]
        if not mala_palabra.strip(): continue
        pattern = re.compile(r'\b' + re.escape(mala_palabra) + r'\b', re.IGNORECASE)
        content = pattern.sub(buena_palabra, content)

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(content)

def marcar_error_en_bd(video_id, mensaje_error):
    try:
        db_s = SessionLocal()
        v_ref = db_s.get(Video, video_id)
        if v_ref: v_ref.status = 'error'
        db_s.commit()
        db_s.close()
        print(f"   ⚠️ Vídeo ID {video_id} marcado como 'error' en BD.")
    except Exception as e:
        print(f"   ⚠️ No se pudo marcar el error en BD: {e}")

# ── 3. CARGAR RECURSOS Y MOUNT DRIVE ────────────────────────
if not os.path.exists('/content/drive/MyDrive'):
    print("📁 Montando Google Drive...")
    drive.mount('/content/drive', force_remount=True)

if 'model' not in dir():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n⚙️ Cargando modelo Stable-Whisper 'large-v3' en {device.upper()}...")
    model = stable_whisper.load_model("large-v3", device=device)  # ✅ large-v3
    print("✓ Modelo cargado en memoria.")
else:
    print("\n⚡ Modelo ya estaba cargado en caché. Reutilizando.")

print("📥 Descargando diccionario desde GitHub...")
url_diccionario = "https://raw.githubusercontent.com/Zerf8/zerf_transcriptor/main/data/diccionario.json"
try:
    DICCIONARIO = requests.get(url_diccionario).json()
    print("✓ Diccionario remoto cargado.")
except:
    print("⚠️ Fallo al cargar diccionario.")
    DICCIONARIO = {}

# ── 4. CONEXIÓN A BASE DE DATOS (TÚNEL SSH) ─────────────────
print("\n🔌 Levantando túnel SSH hacia Hostinger...")
if 'tunnel' in dir() and tunnel.is_active:
    print("   ↩️ Cerrando túnel previo...")
    tunnel.stop()

tunnel = SSHTunnelForwarder(
    (SSH_HOST, SSH_PORT),
    ssh_username=SSH_USER,
    ssh_password=SSH_PASS,
    remote_bind_address=('127.0.0.1', 3306)
)
tunnel.start()
print(f"✓ Túnel activo en puerto local {tunnel.local_bind_port}")

db_url = f"mysql+pymysql://{DB_USER}:{DB_PASS}@127.0.0.1:{tunnel.local_bind_port}/{DB_NAME}?charset=utf8mb4"
engine = create_engine(db_url, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Video(Base):
    __tablename__ = 'videos'
    id = Column(Integer, primary_key=True)
    youtube_id = Column(String(50), unique=True)
    title = Column(String(255))
    upload_date = Column(DateTime)
    status = Column(String(50), default='pending')

class Transcription(Base):
    __tablename__ = 'transcriptions'
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'))
    whisper_srt = Column(Text(4294967295))
    srt_content = Column(Text(4294967295))
    raw_json = Column(Text(4294967295))
    updated_at = Column(DateTime, default=datetime.utcnow)

# ── 5. MOTOR MASIVO CON DRIVE / YOUTUBE FALLBACK ────────────
try:
    session = SessionLocal()
    pendientes = (
        session.query(Video)
        .filter(Video.status.notin_(['completed', 'error']))
        .order_by(Video.upload_date.desc())
        .all()
    )

    if LIMIT_VIDEOS > 0: pendientes = pendientes[:LIMIT_VIDEOS]
    print(f"\n📋 Videos a procesar en esta tanda: {len(pendientes)}")
    session.close()

    for v in pendientes:
        print(f"\n🎬 Procesando: https://www.youtube.com/watch?v={v.youtube_id} (ID DB: {v.id})")
        print(f"   Título: {v.title}")

        # ── Buscar MP3 en Drive por youtube_id dentro del nombre de archivo
        mp3_file = None
        if os.path.exists(FOLDER_AUDIO):
            for filename in os.listdir(FOLDER_AUDIO):
                if v.youtube_id in filename and filename.endswith(".mp3"):
                    mp3_file = os.path.join(FOLDER_AUDIO, filename)
                    break

        audio_temp_descargado = None
        if mp3_file:
            print(f"   ✅ Audio encontrado en Drive: {os.path.basename(mp3_file)}")
        else:
            print(f"   ⚠️ Audio no encontrado en Drive. Descargando con yt-dlp...")
            mp3_file = f"/content/{v.youtube_id}.mp3"
            audio_temp_descargado = mp3_file

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'/content/{v.youtube_id}.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
                'quiet': True, 'nocheckcertificate': True
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={v.youtube_id}"])
                print("   ✓ Audio temporal descargado correctamente.")
            except Exception as e:
                print(f"   ❌ Error al descargar de YouTube: {e}")
                marcar_error_en_bd(v.id, f"Error descarga yt-dlp: {str(e)}")
                continue

        srt_tmp = f"/content/{v.youtube_id}.srt"

        try:
            fecha_subida = str(v.upload_date) if v.upload_date else "2024"
            prompt = get_prompt_for_year(fecha_subida)

            print(f"   🎤 Transcribiendo con Stable-TS en GPU (Año: {fecha_subida[:4]})...")
            t0 = time.time()

            result = model.transcribe(
                mp3_file,
                language="es",
                initial_prompt=prompt,
                vad=True, regroup=True, word_timestamps=True
            )

            result.split_by_length(max_chars=42, max_words=12).to_srt_vtt(
                srt_tmp, word_level=False, segment_level=True
            )
            print(f"   ✓ Transcripción completada en {time.time() - t0:.1f}s")

            apply_dictionary_to_srt(srt_tmp, DICCIONARIO)

            with open(srt_tmp, 'r', encoding='utf-8') as f:
                srt_text = f.read()

            clean_dict = result.to_dict()
            if '_stable_result' in clean_dict: del clean_dict['_stable_result']

            db_session = SessionLocal()
            video_ref = db_session.get(Video, v.id)
            trans_existente = db_session.query(Transcription).filter_by(video_id=v.id).first()

            trans = trans_existente or Transcription(video_id=v.id)
            if not trans_existente: db_session.add(trans)

            trans.whisper_srt = srt_text
            trans.srt_content = srt_text
            trans.raw_json    = json.dumps(clean_dict, ensure_ascii=False)
            trans.updated_at  = datetime.utcnow()
            video_ref.status  = 'completed'

            db_session.commit()
            db_session.close()
            print("   💾 ¡Guardado en la Base de Datos con éxito!")

        except Exception as e:
            print(f"   ❌ Error interno: {str(e)}")
            import traceback; traceback.print_exc()
            marcar_error_en_bd(v.id, str(e))

        finally:
            # Solo borra el MP3 si fue descargado temporalmente, nunca los de Drive
            if audio_temp_descargado and os.path.exists(audio_temp_descargado):
                os.remove(audio_temp_descargado)
            if os.path.exists(srt_tmp):
                os.remove(srt_tmp)
            gc.collect()
            torch.cuda.empty_cache()

finally:
    print("\n✅ Proceso finalizado. Cerrando túnel SSH...")
    tunnel.stop()
