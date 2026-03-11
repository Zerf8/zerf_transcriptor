import requests
from src.models import Video, Transcription, get_engine
from sqlalchemy.orm import sessionmaker

engine = get_engine()
Session = sessionmaker(bind=engine)
session = Session()

# Seleccionar el vídeo más reciente completado que tenga SRT en DB
t = session.query(Transcription).join(Video).filter(Transcription.language == 'es', Transcription.srt_content != None).order_by(Video.upload_date.desc()).first()
if not t:
    print("FATAL: No se ha encontrado ninguna transcripición 'es' original en la Base de Datos.")
else:
    video = session.get(Video, t.video_id)
    print(f"Probando Traducción Local sobre el Vídeo: {video.title} (ID: {video.youtube_id})")
    
    url = f"http://localhost:8000/api/translate/{video.youtube_id}/en"
    print(f"Llamando a {url} ...")
    try:
        r = requests.post(url)
        print("Respuesta API:", r.status_code, r.text)
    except Exception as e:
        print("Error llamando a la API local:", e)
        
session.close()
