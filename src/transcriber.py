"""
Motor de transcripción con Faster-Whisper
Transcribe audio, genera SRT y TXT de forma mucho más rápida en CPU
"""
from faster_whisper import WhisperModel
import os
from typing import Dict, List, Tuple, Optional
from datetime import timedelta


class Transcriber:
    def __init__(self, model_name: str = 'large-v2', language: str = 'es'):
        self.model_name = model_name
        self.language = language
        self.model = None
        # Prompt contextual CRÍTICO para nombres propios
        self.initial_prompt = "Transcripción de análisis del FC Barcelona. Jugadores: Lamine Yamal, Lewandowski, Cubarsí, Fermín, Gavi, Pedri, Araújo, Koundé, Raphinha, Ter Stegen, Pau Víctor, Dani Olmo, Flick."
        print(f"🤖 Inicializando Faster-Whisper modelo '{model_name}' (Configuración Robusta)...")
    
    def load_model(self):
        """Cargar modelo de Faster-Whisper (se hace una sola vez)"""
        if self.model is None:
            # Usar 'int8' para máxima velocidad en CPU
            self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=4)
            print(f"✓ Modelo Faster-Whisper cargado: {self.model_name}")
    
    def transcribe_audio(self, audio_path: str) -> Optional[Dict]:
        """
        Transcribir archivo de audio usando Faster-Whisper
        Retorna: dict compatible con el formato que espera main.py
        """
        self.load_model()
        
        print(f"🎤 Transcribiendo (Modo Fiabilidad): {audio_path}")
        
        try:
            # Faster-whisper devuelve un generador de segmentos
            segments_gen, info = self.model.transcribe(
                audio_path,
                language=self.language,
                beam_size=5,
                word_timestamps=True,
                initial_prompt=self.initial_prompt, # Clave para nombres
                condition_on_previous_text=False,   # Clave anti-bucles
                vad_filter=True,                    # Activado pero suave para no cortar inicios
                vad_parameters=dict(min_silence_duration_ms=500),
                temperature=0.0,                    # Clave anti-alucinaciones "creativas"
                repetition_penalty=1.2              # Clave anti-repeticiones
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
                    'avg_logprob': getattr(s, 'avg_logprob', 0.0)
                }
                if hasattr(s, 'words') and s.words:
                    segment_dict['words'] = [{'word': w.word, 'start': w.start, 'end': w.end} for w in s.words]
                
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

    def normalize(self, w: str) -> str:
        import re
        return re.sub(r'[^\w]','',w.lower())
        
    def ts_to_ms(self, ts: str) -> int:
        ts = ts.strip().replace(',', '.')
        parts = ts.split(':')
        h, m, s = (parts if len(parts) == 3 else ['0'] + parts)
        secs, ms_part = (s.split('.') + ['0'])[:2]
        return int(h)*3600000 + int(m)*60000 + int(secs)*1000 + int(ms_part[:3].ljust(3,'0'))

    def ms_to_srt(self, ms: int) -> str:
        h=ms//3600000; ms%=3600000; m=ms//60000; ms%=60000; s=ms//1000; ms%=1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def clean_vtt_line(self, raw: str) -> str:
        import re, html
        t = re.sub(r'<\d{1,2}:\d{2}:\d{2}\.\d{3}>', '', raw)
        t = re.sub(r'<[^>]+>', '', t)
        t = html.unescape(t)
        t = re.sub(r'\[\s*__\s*\]', '', t)
        return ' '.join(t.split())

    def is_desc_only(self, text: str) -> bool:
        import re
        return len(re.sub(r'\[[^\]]*\]', '', text).strip()) == 0 and len(text.strip()) > 0

    def generate_srt_from_vtt(self, whisper_srt_content: str, vtt_path: str, output_path: str):
        """Alinea el texto de Whisper a los bloques de un VTT existente usando difflib"""
        import re, os, difflib
        
        # 1. Parse VTT
        with open(vtt_path, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
            
        vtt_segments = []
        for block in re.split(r'\n\n+', vtt_content):
            lines = block.strip().splitlines()
            m = None
            for i, line in enumerate(lines):
                m = re.match(r'(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})', line)
                if m:
                    text_lines = lines[i+1:]; break
            if not m: continue
            start_ms, end_ms = self.ts_to_ms(m.group(1)), self.ts_to_ms(m.group(2))
            if end_ms - start_ms < 100: continue
            useful = [l for l in text_lines if l.strip() and l.strip() not in ('\xa0',' ')]
            if not useful: continue
            clean = self.clean_vtt_line(useful[-1])
            if not clean: continue
            vtt_segments.append({'start_ms':start_ms, 'end_ms':end_ms, 'text':clean,
                             'is_desc':self.is_desc_only(clean), 'assigned_words':[]})
                             
        # 2. Parse Whisper
        content = re.sub(r'\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}','', whisper_srt_content)
        content = re.sub(r'^\d+\s*$','',content,flags=re.MULTILINE)
        wh_words = content.split()
        
        # 3. Align
        for seg in vtt_segments: seg['assigned_words'] = []
        yt_words, yt_idx = [], []
        for i, seg in enumerate(vtt_segments):
            if seg['is_desc']: seg['assigned_words']=[seg['text']]; continue
            for w in seg['text'].split():
                if w: yt_words.append(w); yt_idx.append(i)
                
        if yt_words and wh_words:
            matcher = difflib.SequenceMatcher(None,[self.normalize(w) for w in yt_words],[self.normalize(w) for w in wh_words],autojunk=False)
            for tag,i1,i2,j1,j2 in matcher.get_opcodes():
                if tag=='equal':
                    for k in range(j2-j1): vtt_segments[yt_idx[i1+k]]['assigned_words'].append(wh_words[j1+k])
                elif tag=='replace':
                    affected=[]
                    for i in range(i1,i2):
                        if i<len(yt_idx):
                            s=yt_idx[i]
                            if not affected or affected[-1]!=s: affected.append(s)
                    if affected: vtt_segments[affected[0]]['assigned_words'].extend(wh_words[j1:j2])
                    elif vtt_segments: vtt_segments[-1]['assigned_words'].extend(wh_words[j1:j2])
                elif tag=='insert':
                    t=min(i1,len(yt_idx)-1) if yt_idx else 0
                    if yt_idx: vtt_segments[yt_idx[t]]['assigned_words'].extend(wh_words[j1:j2])
                    
        # 4. Write output
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        idx=1
        with open(output_path,'w',encoding='utf-8') as f:
            for seg in vtt_segments:
                text = seg['text'] if seg['is_desc'] else ' '.join(seg['assigned_words']).strip()
                if not text: continue
                f.write(f"{idx}\n{self.ms_to_srt(seg['start_ms'])} --> {self.ms_to_srt(seg['end_ms'])}\n{text}\n\n")
                idx+=1
                
        print(f"✓ Archivo SRT (Alineado a VTT difflib) generado: {output_path}")
    
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
