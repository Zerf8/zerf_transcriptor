import sys
import os
from sqlalchemy.orm import sessionmaker

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.append(project_dir)

from src.models import Video, Transcription, get_engine

def main():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    records = session.query(Transcription).all()
    print(f"Restaurando {len(records)} transcripciones a sus tiempos originales...")
    
    for t in records:
        if t.srt_content:
            t.whisper_srt = t.srt_content
        if t.gemini_text:
            t.temp_refinado_srt = t.gemini_text
            t.refinado_srt = t.gemini_text
            
    try:
        session.commit()
        print("¡Base de datos restaurada con éxito! Todos los tiempos originales de Whisper han vuelto.")
    except Exception as e:
        print(f"Error guardando: {e}")
        session.rollback()

if __name__ == '__main__':
    main()
