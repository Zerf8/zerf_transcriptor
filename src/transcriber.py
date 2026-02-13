"""
Motor de transcripción con Whisper
Transcribe audio, genera SRT y TXT, identifica palabras con baja confianza
"""
import whisper
import os
from typing import Dict, List, Tuple, Optional
from datetime import timedelta


class Transcriber:
    def __init__(self, model_name: str = 'medium', language: str = 'es'):
        self.model_name = model_name
        self.language = language
        self.model = None
        print(f"🤖 Inicializando Whisper modelo '{model_name}'...")
    
    def load_model(self):
        """Cargar modelo de Whisper (se hace una sola vez)"""
        if self.model is None:
            self.model = whisper.load_model(self.model_name)
            print(f"✓ Modelo cargado: {self.model_name}")
    
    def transcribe_audio(self, audio_path: str) -> Optional[Dict]:
        """
        Transcribir archivo de audio
        Retorna: dict con texto completo, segmentos, y metadata
        """
        self.load_model()
        
        print(f"🎤 Transcribiendo: {audio_path}")
        
        try:
            result = self.model.transcribe(
                audio_path,
                language=self.language,
                task='transcribe',
                fp16=False,  # Usar fp32 para compatibilidad CPU
                verbose=True,
                word_timestamps=True  # Importante para SRT preciso
            )
            
            print(f"✓ Transcripción completada")
            return result
            
        except Exception as e:
            print(f"✗ Error en transcripción: {e}")
            return None
    
    def generate_srt(self, segments: List[Dict], output_path: str):
        """Generar archivo SRT con timestamps"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                # Número de subtítulo
                f.write(f"{i}\n")
                
                # Timestamps en formato SRT: HH:MM:SS,mmm --> HH:MM:SS,mmm
                start = self._format_timestamp(segment['start'])
                end = self._format_timestamp(segment['end'])
                f.write(f"{start} --> {end}\n")
                
                # Texto del segmento
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
        """
        Identificar palavras con baja confianza
        Retorna: lista de (palabra, confianza, timestamp)
        """
        low_conf_words = []
        
        for segment in segments:
            # Whisper proporciona avg_logprob que podemos usar como proxy de confianza
            # Valores típicos: -0.1 (alta confianza) a -1.0+ (baja confianza)
            if 'avg_logprob' in segment:
                # Convertir logprob a score 0-1 (aproximado)
                confidence = min(1.0, max(0.0, 1.0 + segment['avg_logprob']))
                
                if confidence < threshold:
                    timestamp = self._format_timestamp(segment['start'])
                    low_conf_words.append((segment['text'].strip(), confidence, timestamp))
        
        return low_conf_words
