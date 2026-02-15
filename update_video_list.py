import yt_dlp
import os
import datetime
import sys

# Añadir directorio raíz al path para importar src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.models import Video, VideoStats, get_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

# Importar notificador
try:
    from notify_telegram import send_message
except ImportError:
    def send_message(msg): print(f"[MOCK TELEGRAM] {msg}")

load_dotenv()

# CONFIGURACIÓN
CHANNEL_URL = "https://www.youtube.com/@ZerfFCB/videos"
LIST_FILE = r"G:\Mi unidad\Transcripts_Barca\lista_maestra_videos.txt" 
MAX_VIDEOS_TO_CHECK = 50 
NOTIFY_EVERY = 100 # Notificar cada X videos procesados

# Setup DB
print(f"DEBUG: Configurando engine para {os.getenv('DB_NAME')}...")
try:
    engine = get_engine()
    # Test connection
    with engine.connect() as conn:
        print("DEBUG: Conexión a DB exitosa!")
        # Check database selected
        res = conn.execute(text("SELECT DATABASE()")).fetchone()
        print(f"DEBUG: Base de datos seleccionada: {res[0]}")
except Exception as e:
    print(f"DEBUG: Error crítico conectando a DB: {e}")
    sys.exit(1)
    
Session = sessionmaker(bind=engine)

def clean_text(text):
    """Limpia texto para que quepa en una línea y no rompa el formato"""
    if not text: return ""
    text = text.replace('\n', ' ').replace('\r', ' ').replace('|', '-')
    return " ".join(text.split())

def sync_to_db(session, info):
    """Sincroniza metadatos de un video con la base de datos"""
    try:
        video_id = info.get('id')
        if not video_id: return

        # Buscar si existe
        video = session.query(Video).filter_by(youtube_id=video_id).first()
        
        # Datos a actualizar
        title = info.get('title', 'Sin Título')
        duration = info.get('duration', 0)
        desc = info.get('description', '')
        upload_date_str = info.get('upload_date') # YYYYMMDD
        
        # Nuevos campos enriquecidos
        thumbnail = info.get('thumbnail')
        tags_list = info.get('tags', [])
        tags = ",".join(tags_list) if tags_list else None
        categories_list = info.get('categories', [])
        category = categories_list[0] if categories_list else None
        
        upload_date = None
        if upload_date_str:
            try:
                upload_date = datetime.datetime.strptime(upload_date_str, '%Y%m%d')
            except:
                pass

        if not video:
            # Crear nuevo
            video = Video(
                youtube_id=video_id,
                title=title,
                duration=duration,
                description=desc,
                upload_date=upload_date,
                channel=info.get('uploader', 'ZerfFCB'),
                status='pending', # O 'backfilled'
                thumbnail=thumbnail,
                tags=tags,
                category=category
            )
            session.add(video)
            # Stats iniciales
            stats = VideoStats(
                video=video, # Relación
                view_count=info.get('view_count', 0),
                like_count=info.get('like_count', 0),
                comment_count=info.get('comment_count', 0)
            )
            session.add(stats)
            print(f"      OK DB: Nuevo video insertado: {video_id}")
        else:
            # Actualizar existente
            video.title = title
            video.description = desc
            if duration: video.duration = duration
            if upload_date: video.upload_date = upload_date
            
            # Actualizar campos enriquecidos
            video.thumbnail = thumbnail
            video.tags = tags
            video.category = category
            
            # Actualizar stats si existen
            if video.stats:
                video.stats.view_count = info.get('view_count', video.stats.view_count)
                video.stats.like_count = info.get('like_count', video.stats.like_count)
                video.stats.comment_count = info.get('comment_count', video.stats.comment_count)
            
            print(f"      OK DB: Video actualizado: {video_id}")
            
        session.commit()
    except Exception as e:
        print(f"      !! DB Error: {e}")
        session.rollback()

def update_list():
    print(f">> Buscando videos nuevos en: {CHANNEL_URL}")
    
    # 1. Leer lista actual para no duplicar
    existing_urls = set()
    if os.path.exists(LIST_FILE):
        with open(LIST_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if '|' in line:
                    url = line.split('|')[0].strip()
                    existing_urls.add(url)
        print(f">> Lista actual cargada: {len(existing_urls)} videos.")
    else:
        print(">> No existe lista previa. Se creará una nueva.")

    # 2. Extraer videos recientes del canal
    ydl_opts = {
        'quiet': True,
        'extract_flat': True, # Solo metadatos, muy rápido
        'playlist_end': MAX_VIDEOS_TO_CHECK,
    }

    new_entries = []
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(CHANNEL_URL, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                    
                    if url not in existing_urls:
                        title = clean_text(entry.get('title', 'Sin Título'))
                        desc = clean_text(entry.get('description', ''))[:200] 
                        
                        # Formato: URL | TITULO | DESCRIPCION
                        entry_line = f"{url} | {title} | {desc}\n"
                        new_entries.append(entry_line)
                        print(f"   + Nuevo encontrado: {title}")
        except Exception as e:
            print(f"!! Error al conectar con YouTube: {e}")
            return

    # 3. Guardar (Prepend: Nuevos primero)
    if new_entries:
        print(f">> Guardando {len(new_entries)} videos nuevos...")
        
        # Leer contenido antiguo
        old_content = ""
        if os.path.exists(LIST_FILE):
            with open(LIST_FILE, 'r', encoding='utf-8') as f:
                old_content = f.read()
        
        # Escribir Nuevos + Antiguos
        with open(LIST_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_entries)
            f.write(old_content)
            
        print(">> Lista actualizada correctamente.")
    else:
        print(">> La lista ya estaba actualizada. No se encontraron videos nuevos.")

    # 4. BACKFILL (Rellenar descripciones faltantes)
    # El usuario pidió explícitamente que "todos tengan la descripción"
    backfill_descriptions()

def backfill_descriptions():
    print("\n>> Iniciando proceso de BACKFILL (Rellenar descripciones faltantes y SYNC DB)...")
    send_message(f"🚀 **Iniciando Backfill**\nComenzando actualización de descripciones y sincronización DB.")
    
    if not os.path.exists(LIST_FILE):
        print("!! No existe el archivo de lista.")
        return

    lines = []
    with open(LIST_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated = False
    new_lines = lines[:] # Copia para modificar

    urls_to_update = []
    indices_map = {} 

    # Obtener IDs ya existentes en DB para no machacar innecesariamente si no hace falta
    # Aunque el usuario pidió actualizar, así que podríamos forzar.
    # Vamos a forzar la actualización de todos los que están en la lista para asegurar uniformidad.
    # Para ser eficientes, procesaremos aquellos que:
    # 1. No tienen descripción en TXT (Prioridad)
    # 2. Sí tienen descripción en TXT, pero queremos asegurar que estén en DB
    
    print(">> Verificando estado de sincronización...")
    
    # IDs de videos en la lista TXT
    videos_in_txt = {}
    for idx, line in enumerate(lines):
        if '|' not in line: continue
        parts = line.split('|')
        url = parts[0].strip()
        has_desc = len(parts) >= 3
        videos_in_txt[url] = {'index': idx, 'has_desc': has_desc, 'line': line}

    # IDs ya en Base de Datos
    existing_db_ids = set()
    try:
        # Extraer solo los youtube_id de la DB
        db_videos = session.query(Video.youtube_id).all()
        existing_db_ids = {v[0] for v in db_videos}
        print(f">> Videos en DB actualmente: {len(existing_db_ids)}")
    except Exception as e:
        print(f"!! Error consultando DB: {e}")

    # Determinar cuáles procesar
    # Procesamos TODO para asegurar datos ricos (tags, thumbnails, etc.)
    # El usuario pidió "todos los datos que puedas sacar" y "hasta que acabemos".
    # Así que ignoramos si ya está en DB o no, y actualizamos todo.
    for url, data in videos_in_txt.items():
        # if not data['has_desc'] or url.split('=')[-1] not in existing_db_ids:
        # IGNORAMOS FILTRO -> TÓ PA DENTRO
        urls_to_update.append(url)
        indices_map[url] = data['index']
        # Si ya tenía descripción pero no estaba en DB, necesitamos preservar la línea original
        # a menos que queramos refrescar datos de YT. Vamos a refrescar para tener stats frescos.

    if not urls_to_update:
        print(">> Nada que procesar.")
        send_message("✅ **Todo listo**\nNo hay videos.")
        return 

    # if urls_to_update:
        # MODO TEST: Limitamos a 5
        # print(f"!! MODO TEST ACTIVADO: Solo se procesarán los primeros 5 de {len(urls_to_update)} videos pendientes.")
        # urls_to_update = urls_to_update[:5]
        # send_message(f"🧪 **MODO TEST**\nProcesando solo 5 videos de prueba...")

    print(f"!! Se encontraron {len(urls_to_update)} videos para actualizar (TXT + DB).")
    
    session = Session() # Abrir sesión DB
    total_processed = 0

    try:
        batch_size = 20 # Restored to normal batch size
        for i in range(0, len(urls_to_update), batch_size):
            batch = urls_to_update[i:i+batch_size]
            print(f"   Batalla {i+1}-{min(i+batch_size, len(urls_to_update))} de {len(urls_to_update)}...")
            
            ydl_opts = {
                'quiet': True,
                'ignoreerrors': True,
                'no_warnings': True,
                'skip_download': True, # Esto saca metadatos full
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for url in batch:
                    try:
                        info = ydl.extract_info(url, download=False)
                        if info:
                            # 1. Actualizar TXT
                            title = clean_text(info.get('title', 'Sin Título'))
                            desc = clean_text(info.get('description', ''))[:200]
                            
                            new_line = f"{url} | {title} | {desc}\n"
                            
                            idx = indices_map.get(url)
                            if idx is not None:
                                new_lines[idx] = new_line
                                updated = True
                                print(f"      OK TXT: {title[:30]}...")
                            
                            # 2. Sincronizar a DB
                            sync_to_db(session, info)
                            
                            total_processed += 1
                            if total_processed % NOTIFY_EVERY == 0:
                                send_message(f"📈 **Progreso Backfill**\nProcesados: {total_processed}/{len(urls_to_update)} videos.\nÚltimo: _{title[:30]}..._")
                            
                    except Exception as e:
                        print(f"      !! Error con {url}: {e}")
    finally:
        session.close()

    if updated:
        with open(LIST_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(">> Backfill completado! Lista guardada.")
        send_message(f"✅ **Proceso Finalizado**\nSe han actualizado {total_processed} videos en TXT y DB.")
    else:       
        print("No se pudieron actualizar los videos pendientes.")
        send_message("⚠️ El proceso finalizó pero no se actualizaron videos (revisa logs).")

if __name__ == "__main__":
    update_list()
