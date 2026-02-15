from src.models import Video, Transcription, Clip, DictionaryEntry, get_engine
from sqlalchemy.orm import sessionmaker

def verify():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    v_count = session.query(Video).count()
    t_count = session.query(Transcription).count()
    c_count = session.query(Clip).count()
    d_count = session.query(DictionaryEntry).count()
    
    print(f"--- VERIFICACIÓN DE DATOS EN HOSTINGER ---")
    print(f"Vídeos: {v_count}")
    print(f"Transcripciones: {t_count}")
    print(f"Clips: {c_count}")
    print(f"Entradas de Diccionario: {d_count}")
    
    if v_count > 0:
        last_v = session.query(Video).order_by(Video.created_at.desc()).first()
        print(f"Último vídeo: {last_v.title}")
    
    session.close()

if __name__ == "__main__":
    verify()
