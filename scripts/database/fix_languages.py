import os
import sys

# Añadir el directorio raíz (zerf_transcriptor) al path de Python
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.models import Transcription, get_engine
from sqlalchemy.orm import sessionmaker

engine = get_engine()
Session = sessionmaker(bind=engine)
session = Session()

try:
    # Set to 'es' any row where language is null or completely empty
    updated = session.query(Transcription).filter(
        (Transcription.language == None) | (Transcription.language == '')
    ).update({"language": "es"}, synchronize_session=False)
    
    session.commit()
    print(f"Éxito: Se han fijado {updated} filas antiguas para que su idioma sea 'es'")
except Exception as e:
    session.rollback()
    print(f"Error fijando la DB: {e}")
finally:
    session.close()
