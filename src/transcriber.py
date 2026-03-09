"""
Motor de transcripción con Faster-Whisper
Transcribe audio, genera SRT y TXT de forma mucho más rápida en CPU
"""
import os
import sys
import json
import gc
import torch
import warnings
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
import stable_whisper
import whisper


class Transcriber:
    def __init__(self, model_name: str = 'large-v2', language: str = 'es', initial_prompt: str = None):
        self.model_name = model_name
        self.language = language
        self.model = None
        self.initial_prompt = initial_prompt or "Hola Culerada, hola Zerfistas. Transcripción de análisis del FC Barcelona. Jugadores: Lamine Yamal, Lewandowski, Cubarsí, Fermín, Gavi, Pedri, Araújo, Koundé, Raphinha, Ter Stegen, Pau Víctor, Dani Olmo, Flick."
        print(f"🤖 Inicializando Whisper de OpenAI modelo '{model_name}' con Stable-TS...")
        
    def load_model(self):
        """Cargar modelo de Whisper clásico a través de stable_whisper"""
        if self.model is None:
            # stable_whisper envuelve el whisper original de OpenAI
            self.model = stable_whisper.load_model(self.model_name)
            print(f"✓ Modelo OpenAI Whisper cargado: {self.model_name} (Stable-TS activado)")
    
    def transcribe_audio(self, audio_path: str) -> Optional[Dict]:
        """
        Transcribir archivo usando stable-ts (OpenAI Whisper interno).
        Retorna: dict compatible con el resto del script (ahora incluirá el objeto result nativo).
        """
        self.load_model()
        
        print(f"🎤 Transcribiendo (OpenAI Whisper + Stable-TS): {audio_path}")
        
        try:
            # stable_whisper transcribe devuelve un objeto WhisperResult
            result = self.model.transcribe(
                audio_path,
                language=self.language,
                beam_size=5,
                initial_prompt=self.initial_prompt,
                condition_on_previous_text=False,
                temperature=0.0,
                vad=True # Estable-ts VAD
            )
            
            print(f"✓ Transcripción completada")
            
            # Guardamos el objeto result entero temporalmente para exportarlo a SRT luego,
            # manteniendo la compatibilidad de texto plano
            return {
                'text': result.text.strip(),
                'segments': result.segments_to_dicts(),
                'language': result.language,
                '_stable_result': result # Referencia oculta para exportar SRT perfecto
            }
            
        except Exception as e:
            print(f"✗ Error en transcripción Whisper: {e}")
            return None
    
    def generate_srt(self, result_dict: Dict, output_path: str):
        """Generar archivo SRT con timestamps usando stable-ts nativo y borrando alineadores"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Extraemos el objeto propio de stable_whisper
        stable_result = result_dict.get('_stable_result')
        if stable_result:
            stable_result.to_srt_vtt(output_path, word_level=False)
            print(f"✓ Archivo SRT (Stable-TS Exacto) generado: {output_path}")
        else:
            # Fallback en caso de que no venga el objeto por algún motivo
            content = self.generate_srt_string(result_dict.get('segments', []))
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Archivo SRT (Fallback básico) generado: {output_path}")

    def generate_srt_string(self, segments: List[Dict]) -> str:
        """Generar contenido SRT como string"""
        lines = []
        for i, segment in enumerate(segments, 1):
            start = self._format_timestamp(segment['start'])
            end = self._format_timestamp(segment['end'])
            lines.append(f"{i}\n{start} --> {end}\n{segment['text'].strip()}\n")
        return "\n".join(lines)

    def generate_srt_from_vtt(self, whisper_srt_content: str, vtt_path: str, output_path: str):
        """Ignorado. Usando stable-ts ya no se alineará con VTT, los tiempos de Whisper serán perfectos"""
        print(f"✓ generate_srt_from_vtt anulado. Los tiempos del SRT ya son perfectos con stable-ts.")
    
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
