"""
Generador de sugerencias de corrección
Analiza el contexto y propone mejoras al diccionario
"""
import json
import os
from typing import Dict, List, Tuple
from datetime import datetime


class CorrectionSuggester:
    def __init__(self):
        # Palabras clave para detectar contexto FCB
        self.fcb_keywords = [
            'barça', 'barcelona', 'fc barcelona', 'camp nou', 'montjuic',
            'gol', 'partido', 'liga', 'champions', 'copa', 'clásico',
            'jugador', 'entrenador', 'equipo', 'afición', 'culer', 'culé'
        ]
    
    def analyze_context(self, text: str) -> Dict:
        """Analizar el contexto del texto"""
        text_lower = text.lower()
        
        # Detectar menciones de FCB
        fcb_mentions = sum(1 for kw in self.fcb_keywords if kw in text_lower)
        is_fcb_context = fcb_mentions > 0
        
        return {
            'is_fcb_context': is_fcb_context,
            'fcb_mentions': fcb_mentions,
            'text_length': len(text)
        }
    
    def suggest_corrections(self, 
                          low_confidence_words: List[Tuple[str, float, str]], 
                          full_text: str,
                          metadata: Dict) -> List[Dict]:
        """
        Generar sugerencias de corrección basadas en palabras de baja confianza
        """
        context = self.analyze_context(full_text)
        suggestions = []
        
        for word, confidence, timestamp in low_confidence_words:
            # Extraer contexto alrededor de la palabra
            word_context = self._extract_context(full_text, word)
            
            suggestion = {
                'timestamp': timestamp,
                'texto_original': word,
                'confianza': round(confidence, 2),
                'contexto': word_context,
                'sugerencia': self._suggest_correction(word, word_context, context),
                'razon': self._explain_suggestion(word, context)
            }
            
            suggestions.append(suggestion)
        
        return suggestions
    
    def _extract_context(self, text: str, word: str, window: int = 50) -> str:
        """Extraer texto alrededor de una palabra"""
        try:
            pos = text.lower().find(word.lower())
            if pos == -1:
                return text[:100]  # Si no se encuentra, retornar inicio
            
            start = max(0, pos - window)
            end = min(len(text), pos + len(word) + window)
            context = text[start:end].strip()
            
            # Añadir elipsis si es necesario
            if start > 0:
                context = "..." + context
            if end < len(text):
                context = context + "..."
            
            return context
        except:
            return text[:100]
    
    def _suggest_correction(self, word: str, context: str, full_context: Dict) -> str:
        """Sugerir una corrección para una palabra"""
        word_lower = word.lower()
        
        # Casos comunes de transcripción errónea de nombres del Barça
        common_mistakes = {
            'levan doski': 'Lewandowski',
            'levan': 'Lewandowski',
            'ches ni': 'Szczęsny',
            'cubrir si': 'Cubarsí',
            'cubar si': 'Cubarsí',
            'conde': 'Koundé',
            'kun de': 'Koundé',
            'rapi ña': 'Raphinha',
            'lami ne': 'Lamine',
            'yamal': 'Yamal',
            'joan garcia': 'Joan García',
            'joan laporta': 'Joan Laporta'
        }
        
        # Buscar coincidencias parciales
        for mistake, correction in common_mistakes.items():
            if mistake in word_lower:
                return correction
        
        # Si está en contexto FCB y empieza con mayúscula, probablemente es nombre
        if full_context['is_fcb_context'] and word and word[0].isupper():
            return f"{word} (verificar ortografía - posible nombre de jugador)"
        
        # Por defecto, sugerir revisar
        return f"{word} (revisar)"
    
    def _explain_suggestion(self, word: str, context: Dict) -> str:
        """Explicar por qué se sugiere una corrección"""
        if context['is_fcb_context']:
            return "Baja confianza en contexto FC Barcelona - posible nombre de jugador"
        return "Baja confianza de transcripción"
    
    def generate_review_report(self, 
                               suggestions: List[Dict], 
                               metadata: Dict,
                               output_path: str):
        """Generar reporte JSON de sugerencias para revisión manual"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        report = {
            'video_title': metadata.get('title', 'Sin título'),
            'fecha_proceso': datetime.now().isoformat(),
            'total_sugerencias': len(suggestions),
            'sugerencias': suggestions
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Reporte de sugerencias generado: {output_path}")
        print(f"  Total de sugerencias: {len(suggestions)}")
