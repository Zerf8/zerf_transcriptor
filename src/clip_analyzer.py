"""
Analizador de clips
Detecta segmentos de alta intensidad o interés para sugerir como clips
"""
from typing import List, Dict, Tuple
import re

class ClipAnalyzer:
    def __init__(self):
        # Palabras clave de alta intensidad/emoción
        self.intensity_keywords = [
            'gol', 'golazo', 'increíble', 'ojo', 'cuidado', 'madre mía',
            'hostia', 'brutal', 'espectacular', 'locura', 'impresionante',
            'penalti', 'polémica', 'dios', 'vaya tela', 'infame'
        ]
        
        # Palabras de ENFADO / INSULTOS / VERBORREA INCENDIARIA
        self.insult_keywords = [
            'puta', 'mierda', 'vergüenza', 'robo', 'escándalo', 'basura', 
            'imbécil', 'tonto', 'payaso', 'subnormal', 'asco', 'lamentable',
            'sinvergüenza', 'atracos', 'joder', 'cojones', 'mongolo', 
            'cerdo', 'rata', 'inútil'
        ]

        # Palabras de RISA
        self.laugh_keywords = [
            'jajaja', 'jejeje', 'me parto', 'descojono', 'qué risa', 
            'no puedo más', 'jaja'
        ]
        
        # Palabras que suelen indicar inicio de opinión fuerte
        self.opinion_starters = [
            'yo creo que', 'la verdad es que', 'sinceramente', 
            'no entiendo', 'es vergonzoso', 'tengo que decir',
            'esto es inaceptable'
        ]

    def analyze_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        Analizar segmentos transcritos para encontrar candidatos a clips
        Retorna: Lista de clips sugeridos
        """
        raw_candidates = []
        window_duration = 45.0  # Analizar ventanas de ~45 segundos
        step = 15.0  # Deslizar ventana cada 15 segundos
        
        # 1. Ventana deslizante basada en TIEMPO
        current_time = 0.0
        max_time = segments[-1]['end'] if segments else 0
        
        while current_time < max_time:
            window_end = current_time + window_duration
            
            # Obtener segmentos dentro de esta ventana de tiempo
            window_segments = [
                s for s in segments 
                if s['start'] >= current_time and s['end'] <= window_end
            ]
            
            if not window_segments:
                current_time += step
                continue
                
            # Unir texto
            text_block = " ".join([s['text'].strip() for s in window_segments])
            score, reason, tags = self._calculate_interest_score(text_block)
            
            # Umbral mínimo para ser considerado clip
            if score >= 5:
                raw_candidates.append({
                    'start': window_segments[0]['start'],
                    'end': window_segments[-1]['end'],
                    'text': text_block,
                    'score': score,
                    'reason': reason,
                    'tags': tags
                })
            
            current_time += step
            
        # 2. Fusionar clips solapados o muy cercanos
        merged_clips = []
        if raw_candidates:
            # Ordenar por tiempo de inicio
            raw_candidates.sort(key=lambda x: x['start'])
            
            current_clip = raw_candidates[0]
            
            for next_clip in raw_candidates[1:]:
                # Si se solapan o están muy cerca (< 5s)
                if next_clip['start'] <= current_clip['end'] + 5.0:
                    # Fusionar: extender final y quedarse con el mejor score/reason
                    current_clip['end'] = max(current_clip['end'], next_clip['end'])
                    
                    # Unir tags (sin duplicados)
                    combined_tags = set(current_clip['tags'])
                    combined_tags.update(next_clip['tags'])
                    current_clip['tags'] = list(combined_tags)

                    if next_clip['score'] > current_clip['score']:
                        current_clip['score'] = next_clip['score']
                        # Acumular razones si son diferentes
                        if next_clip['reason'] not in current_clip['reason']:
                            current_clip['reason'] += ", " + next_clip['reason']
                else:
                    merged_clips.append(current_clip)
                    current_clip = next_clip
            merged_clips.append(current_clip)
        
        # 3. Formatear salida final (SIN LÍMITE DE NÚMERO)
        final_clips = []
        # Ordenar por tiempo (crónico) para facilitar edición
        merged_clips.sort(key=lambda x: x['start'])
        
        for clip in merged_clips:
             final_clips.append({
                'start_time': self._format_timestamp(clip['start']),
                'end_time': self._format_timestamp(clip['end']),
                'duration': f"{int(clip['end'] - clip['start'])}s",
                'score': clip['score'],
                'reason': clip['reason'],
                'tags': clip.get('tags', []),
                'text_preview': clip['text']
            })
            
        return final_clips

    def _calculate_interest_score(self, text: str) -> Tuple[int, str, List[str]]:
        """Calcular puntaje, razones y etiquetas"""
        score = 0
        reasons = []
        tags = set()
        text_lower = text.lower()
        
        # 1. INSULTOS / VERBORREA (+5 puntos, muy importante)
        for kw in self.insult_keywords:
            if kw in text_lower:
                score += 5
                tags.add("#ira")
                tags.add("#polemica")
                tags.add("#rant")
                if "🔥 Verborrea/Enfado" not in reasons: reasons.append("🔥 Verborrea/Enfado")
        
        # 2. RISAS (+4 puntos)
        for kw in self.laugh_keywords:
            if kw in text_lower:
                score += 4
                tags.add("#humor")
                tags.add("#risas")
                if "😂 Risas" not in reasons: reasons.append("😂 Risas")

        # 3. Palabras de intensidad (+2 puntos cada una)
        for kw in self.intensity_keywords:
            count = text_lower.count(kw)
            if count > 0:
                score += (count * 2)
                tags.add("#highlights")
                if kw in ['gol', 'golazo']:
                    tags.add("#gol")
                if "Intensidad" not in reasons: reasons.append("Intensidad")
        
        # 4. Opinión fuerte (+3 puntos)
        for kw in self.opinion_starters:
            if kw in text_lower:
                score += 3
                tags.add("#opinion")
                if "Opinión fuerte" not in reasons: reasons.append("Opinión fuerte")

        # 5. ETIQUETADO DE PERSONAS (Nombres clave)
        nombres_tags = {
            'lamine': '#Lamine', 'yamal': '#Lamine', 'la min': '#Lamine',
            'lewandowski': '#Lewandowski', 'lewy': '#Lewandowski',
            'pedri': '#Pedri', 'gavi': '#Gavi',
            'frenkie': '#Frenkie', 'jong': '#Frenkie',
            'araujo': '#Araujo', 'kounde': '#Kounde',
            'balde': '#Balde', 'cubarsi': '#Cubarsi',
            'ferran': '#Ferran', 'raphinha': '#Raphinha',
            'hansi': '#HansiFlick', 'flick': '#HansiFlick',
            'laporta': '#Laporta', 'xavi': '#Xavi',
            'ter stegen': '#TerStegen', 'iñaki': '#InakiPena',
            'mateu': '#MateuLahoz', 'lahoz': '#MateuLahoz',
            'madrid': '#RealMadrid', 'vinicius': '#Vinicius',
            'mbappe': '#Mbappe', 'albacete': '#Albacete',
            'rashford': '#Rashford', 'paco jemez': '#PacoJemez',
            'eder sarabia': '#EderSarabia'
        }
        for nombre, tag in nombres_tags.items():
            if nombre in text_lower:
                tags.add(tag)
        
        # 6. Repeticiones rápidas (signo de énfasis) (+3 puntos)
        if re.search(r'\b(\w+)\s+\1\s+\1\b', text_lower):
            score += 3
            tags.add("#reaccion")
            if "Repetición enfática" not in reasons: reasons.append("Repetición enfática")
            
        # 7. Signos de exclamación (+1 punto)
        score += text.count('!')
        
        return score, ", ".join(reasons), list(tags)

    def _format_timestamp(self, seconds: float) -> str:
        """HH:MM:SS"""
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

    def save_clips_report(self, clips: List[Dict], output_path: str):
        """Guardar reporte de clips sugeridos"""
        import json
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'suggested_clips': clips}, f, ensure_ascii=False, indent=2)
            
        print(f"✓ Reporte de clips generado: {output_path}")
