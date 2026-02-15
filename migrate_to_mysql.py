import json
import os
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from src.models import Video, Transcription, Clip, DictionaryEntry, get_engine, Base

def migrate():
    # 1. Cargar datos de archivos
    state_path = 'data/processing_state.json'
    dict_path = 'data/diccionario.json'
    
    if not os.path.exists(state_path):
        print("❌ No se encontró el archivo de estado.")
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        state_data = json.load(f)
        
    with open(dict_path, 'r', encoding='utf-8') as f:
        dict_data = json.load(f)

    # 2. Configurar conexión
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    print(f"🚀 Iniciando migración a {os.getenv('DB_HOST')}...")

    # 3. Migrar Diccionario
    print("📚 Migrando diccionario...")
    for term, correction in dict_data.get('correcciones_aprendidas', {}).items():
        # Evitar duplicados
        exists = session.query(DictionaryEntry).filter_by(term=term).first()
        if not exists:
            new_entry = DictionaryEntry(term=term, correction=correction, category='general')
            session.add(new_entry)
    session.commit()

    # 4. Migrar Vídeos y Transcripciones
    videos_procesados = state_data.get('videos_procesados', [])
    print(f"🎬 Migrando {len(videos_procesados)} vídeos procesados...")
    
    for v_data in videos_procesados:
        url = v_data.get('url', '')
        yt_id = url.split('v=')[-1] if 'v=' in url else url.split('/')[-1]
        
        # Verificar si ya existe
        exists = session.query(Video).filter_by(youtube_id=yt_id).first()
        if exists:
            continue
            
        metadata = v_data.get('metadata', {})
        fecha_proceso = v_data.get('fecha_proceso', '')
        
        # Crear Objeto Video
        video = Video(
            youtube_id=yt_id,
            title=metadata.get('title', 'Sin título'),
            duration=metadata.get('duration', 0),
            status='completed',
            updated_at=datetime.fromisoformat(fecha_proceso) if fecha_proceso else datetime.utcnow()
        )
        session.add(video)
        session.flush() # Para obtener el ID del vídeo

        # Intentar cargar contenido de archivos para la transcripción
        whisper_text = ""
        txt_path = metadata.get('txt_path', '')
        if txt_path and os.path.exists(txt_path):
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    whisper_text = f.read()
            except: pass

        srt_content = ""
        srt_path = metadata.get('srt_path', '')
        if srt_path and os.path.exists(srt_path):
            try:
                with open(srt_path, 'r', encoding='utf-8') as f:
                    srt_content = f.read()
            except: pass

        raw_json = ""
        raw_path = metadata.get('raw_path', '')
        if raw_path and os.path.exists(raw_path):
            try:
                with open(raw_path, 'r', encoding='utf-8') as f:
                    raw_json = f.read()
            except: pass

        # Crear Transcripción
        transcription = Transcription(
            video_id=video.id,
            whisper_text=whisper_text,
            srt_content=srt_content,
            raw_json=raw_json
        )
        session.add(transcription)

        # Cargar Clips si existen
        clips_path = metadata.get('clips_path', '')
        if clips_path and os.path.exists(clips_path):
            try:
                with open(clips_path, 'r', encoding='utf-8') as f:
                    clips_data = json.load(f)
                    for c in clips_data.get('suggested_clips', []):
                        clip = Clip(
                            video_id=video.id,
                            start_time=c.get('start_time'),
                            end_time=c.get('end_time'),
                            text_preview=c.get('text_preview'),
                            score=c.get('score'),
                            reason=c.get('reason'),
                            tags=",".join(c.get('tags', [])),
                            source='rules'
                        )
                        session.add(clip)
            except: pass

    # 5. Migrar Vídeos Fallidos
    videos_fallidos = state_data.get('videos_fallidos', [])
    print(f"❌ Migrando {len(videos_fallidos)} vídeos fallidos...")
    for v_data in videos_fallidos:
        url = v_data.get('url', '')
        yt_id = url.split('v=')[-1] if 'v=' in url else url.split('/')[-1]
        
        exists = session.query(Video).filter_by(youtube_id=yt_id).first()
        if not exists:
            video = Video(
                youtube_id=yt_id,
                status='failed',
                last_error=v_data.get('error', 'Error desconocido')
            )
            session.add(video)

    session.commit()
    print("✅ Migración completada exitosamente.")
    session.close()

if __name__ == "__main__":
    migrate()
