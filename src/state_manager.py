"""
Gestor de estado de procesamiento (Versión MySQL)
Rastrea qué videos han sido procesados usando la Base de Datos centralizada.
También se encarga de subir los resultados (transcripciones/clips) a la DB al finalizar.
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import sessionmaker
from src.models import get_engine, Video, Transcription, Clip

class StateManager:
    def __init__(self, state_file: str = None):
        # state_file se mantiene por compatibilidad pero no se usa
        self.engine = get_engine()
        self.Session = sessionmaker(bind=self.engine)
    
    def _extract_id(self, url: str) -> str:
        """Extraer ID de YouTube de la URL"""
        if "v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        return url
    
    def mark_processed(self, url: str, metadata: Dict, execution_stats: Optional[Dict] = None):
        """
        Marcar video como procesado y GUARDAR resultados en la DB.
        Lee los archivos locales generados por main.py y los sube.
        """
        yid = self._extract_id(url)
        session = self.Session()
        
        try:
            video = session.query(Video).filter_by(youtube_id=yid).first()
            if not video:
                # Si no existe (raro si se sincronizó), lo creamos
                video = Video(
                    youtube_id=yid,
                    title=metadata.get('title'),
                    duration=metadata.get('duration'),
                    status='processing'
                )
                session.add(video)
                session.flush() # Para tener ID
            
            # 1. Guardar Transcripción
            srt_path = metadata.get('srt_path')
            raw_path = metadata.get('raw_path')
            txt_refinado_path = metadata.get('txt_refinado_path')
            
            srt_content = ""
            if srt_path and os.path.exists(srt_path):
                with open(srt_path, 'r', encoding='utf-8') as f:
                    srt_content = f.read()

            gemini_text = None
            if txt_refinado_path and os.path.exists(txt_refinado_path):
                with open(txt_refinado_path, 'r', encoding='utf-8') as f:
                    gemini_text = f.read()

            youtube_vtt_path = metadata.get('youtube_vtt_path')
            
            # Robust original subtitle detection (VTT preferred, SRT fallback from YT)
            if not youtube_vtt_path or not os.path.exists(youtube_vtt_path):
                # Intentar adivinar por ID del video en la carpeta videos/
                potential_files = [
                    f"videos/{yid}.es.vtt", 
                    f"videos/{yid}.en.vtt",
                    f"videos/{yid}.es.srt", # Fallback si YT convierte a SRT
                    f"videos/{yid}.en.srt"
                ]
                for pf in potential_files:
                    if os.path.exists(pf):
                        youtube_vtt_path = pf
                        break
                
                if not youtube_vtt_path or not os.path.exists(youtube_vtt_path):
                    # Buscar cualquier .vtt o .srt que empiece con el ID
                    import glob
                    files = glob.glob(f"videos/{yid}*.vtt") + glob.glob(f"videos/{yid}*.srt")
                    # Filtrar para no coger el de whisper si es posible, aunque por ID suele ser único
                    if files:
                        youtube_vtt_path = files[0]

            vtt_content = None
            if youtube_vtt_path and os.path.exists(youtube_vtt_path):
                with open(youtube_vtt_path, 'r', encoding='utf-8') as f:
                    vtt_content = f.read()

            raw_content = ""
            whisper_text = ""
            language = "es"
            
            if raw_path and os.path.exists(raw_path):
                with open(raw_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                    try:
                        data = json.loads(raw_content)
                        whisper_text = data.get('text', '')
                        language = data.get('language', 'es')
                    except: pass
            
            # Borrar transcripción previa si existe
            session.query(Transcription).filter_by(video_id=video.id).delete()
            
            transcription = Transcription(
                video_id=video.id,
                whisper_text=whisper_text,
                gemini_text=gemini_text,
                srt_content=srt_content,
                raw_json=raw_content,
                vtt=vtt_content,
                whisper_srt=srt_content,
                temp_refinado_srt=gemini_text,
                language=language
            )
            session.add(transcription)
            
            # 2. Guardar Clips (Reglas + AI)
            # Borrar clips previos antes de añadir los nuevos
            session.query(Clip).filter_by(video_id=video.id).delete()

            clips_paths = [metadata.get('clips_path'), metadata.get('clips_ai_path')]
            
            for path in clips_paths:
                if not path or not os.path.exists(path):
                    continue
                
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        clips_data = json.load(f)
                    
                    clips_list = []
                    source = 'rules' if 'ai' not in path else 'ai'
                    
                    if isinstance(clips_data, list):
                        clips_list = clips_data
                    elif isinstance(clips_data, dict):
                        clips_list = clips_data.get('clips') or clips_data.get('suggested_clips') or []
                    
                    for c in clips_list:
                        clip = Clip(
                            video_id=video.id,
                            start_time=c.get('start_time'),
                            end_time=c.get('end_time'),
                            start_seconds=c.get('start_seconds'),
                            end_seconds=c.get('end_seconds'),
                            text_preview=c.get('text_preview', c.get('title', c.get('reason', ''))),
                            score=c.get('score', 0),
                            reason=c.get('reason', ''),
                            tags=json.dumps(c.get('tags', [])) if isinstance(c.get('tags'), list) else c.get('tags', '[]'),
                            source=source
                        )
                        session.add(clip)
                except Exception as clip_err:
                    print(f"⚠️ Error procesando clips en {path}: {clip_err}")
            
            # 3. Actualizar Estado
            video.status = 'completed'
            video.last_error = None
            video.updated_at = datetime.utcnow()
            
            session.commit()
            print(f"✅ [DB] Datos guardados en MySQL para {yid}")
            
        except Exception as e:
            session.rollback()
            print(f"❌ [DB] Error guardando estado: {e}")
            raise e
        finally:
            session.close()

    def mark_failed(self, url: str, error: str):
        """Marcar video como fallido en DB"""
        yid = self._extract_id(url)
        session = self.Session()
        try:
            video = session.query(Video).filter_by(youtube_id=yid).first()
            if video:
                video.status = 'failed'
                video.last_error = str(error)
                video.updated_at = datetime.utcnow()
                session.commit()
                print(f"⚠️ [DB] Marcado como fallido: {yid}")
        except Exception as e:
            print(f"❌ [DB] Error marcando fallo: {e}")
        finally:
            session.close()

    def is_processed(self, url: str) -> bool:
        """Verificar si ya existe y está completado"""
        yid = self._extract_id(url)
        session = self.Session()
        try:
            video = session.query(Video).filter_by(youtube_id=yid).first()
            # Consideramos 'migrated' también como procesado
            return video and video.status in ['completed', 'migrated']
        finally:
            session.close()

    def get_pending_urls(self, all_urls: List[str]) -> List[str]:
        """
        Filtra la lista de URLs dada, quitando las que ya están en DB con status completed/migrated.
        (Mantenido por compatibilidad pero se recomienda usar get_pending_videos_from_db)
        """
        session = self.Session()
        try:
            processed = session.query(Video.youtube_id).filter(
                Video.status.in_(['completed', 'migrated'])
            ).all()
            processed_ids = {p[0] for p in processed}
            
            pending = []
            for url in all_urls:
                yid = self._extract_id(url)
                if yid not in processed_ids:
                    pending.append(url)
            
            return pending
        finally:
            session.close()

    def get_pending_videos_from_db(self, limit: int = 10) -> List[str]:
        """Busca vídeos con status 'pending' en la DB y devuelve sus URLs."""
        session = self.Session()
        try:
            pending_videos = session.query(Video).filter(Video.status == 'pending').limit(limit).all()
            urls = [f"https://www.youtube.com/watch?v={v.youtube_id}" for v in pending_videos]
            return urls
        finally:
            session.close()

    def get_processing_stats(self) -> Dict:
        """Obtener estadísticas desde la DB"""
        session = self.Session()
        try:
            total_processed = session.query(Video).filter(Video.status.in_(['completed', 'migrated'])).count()
            total_failed = session.query(Video).filter(Video.status == 'failed').count()
            # Pendientes no es fácil de saber sin la lista maestra, pero podemos contar 'pending' en la DB
            # aunque get_pending_urls usa la lista externa. Devolvemos 0 o un estimado.
            total_processing = session.query(Video).filter(Video.status == 'processing').count()
            
            return {
                'total_procesados': total_processed,
                'total_fallidos': total_failed,
                'videos_en_proceso': total_processing,
                'total_pendientes': 'Consultar lista maestra'
            }
        finally:
            session.close()
