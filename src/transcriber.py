"""
Motor de transcripción con Faster-Whisper
Transcribe audio, genera SRT y TXT de forma mucho más rápida en CPU
"""
from faster_whisper import WhisperModel
import os
from typing import Dict, List, Tuple, Optional
from datetime import timedelta


class Transcriber:
    def __init__(self, model_name: str = 'medium', language: str = 'es'):
        self.model_name = model_name
        self.language = language
        self.model = None
        print(f"🤖 Inicializando Faster-Whisper modelo '{model_name}'...")
    
    def load_model(self):
        """Cargar modelo de Faster-Whisper (se hace una sola vez)"""
        if self.model is None:
            # Usar 'int8' para máxima velocidad en CPU, o 'float16' si hubiera GPU
            self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=4)
            print(f"✓ Modelo Faster-Whisper cargado: {self.model_name}")
    
    def transcribe_audio(self, audio_path: str) -> Optional[Dict]:
        """
        Transcribir archivo de audio usando Faster-Whisper
        Retorna: dict compatible con el formato que espera main.py
        """
        self.load_model()
        
        print(f"🎤 Transcribiendo (Modo Turbo): {audio_path}")
        
        try:
            # Faster-whisper devuelve un generador de segmentos
            segments_gen, info = self.model.transcribe(
                audio_path,
                language=self.language,
                beam_size=5,
                word_timestamps=True
            )
            
            # Convertir generador a lista de diccionarios para compatibilidad
            segments = []
            full_text = ""
            
            last_reported_time = -10
            for s in segments_gen:
                segment_dict = {
                    'start': s.start,
                    'end': s.end,
                    'text': s.text,
                    'avg_logprob': s.avg_logprob
                }
                segments.append(segment_dict)
                full_text += s.text
                
                # Reportar progreso cada 10 segundos de audio
                if s.end - last_reported_time >= 10:
                    mins = int(s.end // 60)
                    secs = int(s.end % 60)
                    print(f"   [Progreso] {mins:02d}:{secs:02d} transcritos...")
                    last_reported_time = s.end
            
            print(f"✓ Transcripción Turbo completada")
            return {
                'text': full_text.strip(),
                'segments': segments,
                'language': info.language
            }
            
        except Exception as e:
            print(f"✗ Error en transcripción Faster: {e}")
            return None
    
    def generate_srt(self, segments: List[Dict], output_path: str):
        """Generar archivo SRT con timestamps"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                f.write(f"{i}\n")
                start = self._format_timestamp(segment['start'])
                end = self._format_timestamp(segment['end'])
                f.write(f"{start} --> {end}\n")
                f.write(f"{segment['text'].strip()}\n\n")
        
        print(f"✓ Archivo SRT generado: {output_path}")
    
    def _format_timestamp(self, seconds: float) -> str:
        """Convertir segundos a formato SRT: HH:MM:SS,mmm"""
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        secs = int(td.total_seconds() % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def generate_txt(self, text: str, output_path: str):
        """Generar archivo de texto plano"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"✓ Archivo TXT generado: {output_path}")
    
    def get_low_confidence_words(self, segments: List[Dict], threshold: float = 0.7) -> List[Tuple[str, float, str]]:
        """Identificar palabras con baja confianza"""
        low_conf_words = []
        for segment in segments:
            if 'avg_logprob' in segment:
                # Aproximación de confianza
                confidence = min(1.0, max(0.0, 1.0 + segment['avg_logprob']))
                if confidence < threshold:
                    timestamp = self._format_timestamp(segment['start'])
                    low_conf_words.append((segment['text'].strip(), confidence, timestamp))
        return low_conf_words
