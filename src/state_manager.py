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
            raw_path = metadata.get('raw_path') # raw_json_path en main.py
            
            srt_content = ""
            if srt_path and os.path.exists(srt_path):
                with open(srt_path, 'r', encoding='utf-8') as f:
                    srt_content = f.read()

            raw_content = ""
            whisper_text = ""
            language = "es"
            gemini_text = None
            
            # Intentar leer texto refinado si existe (no pasa en metadata explícitamente pero podemos deducirlo)
            # main.py no pasa 'txt_refinado_path' en metadata, pero podemos intentar buscarlo
            # Basado en la lógica de main.py: output/transcripciones/txt/{output_name}_refinado.txt
            
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
                gemini_text=None, # Se podría mejorar pasando esto en metadata
                srt_content=srt_content,
                raw_json=raw_content,
                language=language
            )
            session.add(transcription)
            
            # 2. Guardar Clips
            clips_path = metadata.get('clips_path')
            if clips_path and os.path.exists(clips_path):
                # Borrar clips previos
                session.query(Clip).filter_by(video_id=video.id).delete()
                
                with open(clips_path, 'r', encoding='utf-8') as f:
                    clips_data = json.load(f)
                
                clips_list = []
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
                        text_preview=c.get('text_preview', c.get('title', '')),
                        score=c.get('score', 0),
                        reason=c.get('reason', ''),
                        tags=json.dumps(c.get('tags', [])),
                        source='ai'
                    )
                    session.add(clip)
            
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
        Optimización: Hace una sola query para traer todos los IDs procesados.
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
