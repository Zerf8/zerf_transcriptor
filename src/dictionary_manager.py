"""
Gestor de diccionario personalizado
Carga, aplica y actualiza correcciones del diccionario
"""
import json
import os
import re
from typing import Dict, List, Tuple


class DictionaryManager:
    def __init__(self, dict_file: str = 'data/diccionario.json'):
        self.dict_file = dict_file
        self.dictionary = self._load_dictionary()
    
    def _load_dictionary(self) -> Dict:
        """Cargar diccionario desde archivo JSON"""
        if os.path.exists(self.dict_file):
            with open(self.dict_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'nombres_propios': {},
            'expresiones_zerf': {},
            'expresiones_catalan': {},
            'correcciones_aprendidas': {}
        }
    
    def save_dictionary(self):
        """Guardar diccionario a archivo JSON"""
        os.makedirs(os.path.dirname(self.dict_file), exist_ok=True)
        with open(self.dict_file, 'w', encoding='utf-8') as f:
            json.dump(self.dictionary, f, ensure_ascii=False, indent=2)
    
    def apply_corrections(self, text: str) -> str:
        """Aplicar correcciones del diccionario al texto transcrito"""
        # Nota: Se ha desactivado temporalmente Fuzzy Matching por rendimiento
        # Se confía en la lista extensa de correcciones exactas (regex)
        
        corrected_text = text
        
        # Combinar todas las categorías del diccionario
        all_corrections = {}
        for category in ['nombres_propios', 'expresiones_zerf', 'expresiones_catalan', 'correcciones_aprendidas']:
            if category in self.dictionary:
                all_corrections.update(self.dictionary[category])
        
        # Aplicar correcciones con REGEX (rápido y eficiente)
        # Ordenamos por longitud descendente para evitar que reemplazos cortos rompan los largos
        sorted_corrections = sorted(all_corrections.items(), key=lambda x: len(x[0]), reverse=True)
        
        for wrong, correct in sorted_corrections:
            if isinstance(correct, list): correct = correct[0]
            
            # Usar \b para asegurar palabra completa, flags=re.IGNORECASE
            pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
            corrected_text = pattern.sub(correct, corrected_text)
            
        return corrected_text
    
    def suggest_additions(self, low_confidence_words: List[Tuple[str, float]], context: str) -> List[Dict]:
        """Sugerir nuevas entradas para el diccionario basadas en palabras con baja confianza"""
        suggestions = []
        
        for word, confidence in low_confidence_words:
            # Buscar si ya existe en el diccionario
            word_lower = word.lower()
            already_exists = any(
                word_lower in category.keys()
                for category in self.dictionary.values()
                if isinstance(category, dict)
            )
            
            if not already_exists:
                suggestions.append({
                    'palabra': word,
                    'confianza': confidence,
                    'contexto': context,
                    'sugerencia_categoria': self._suggest_category(word, context)
                })
        
        return suggestions
    
    def _suggest_category(self, word: str, context: str) -> str:
        """Sugerir en qué categoría debería ir una palabra"""
        word_lower = word.lower()
        
        # Detectar si parece nombre de jugador (mayúscula inicial, en contexto futbolístico)
        if word[0].isupper() and any(kw in context.lower() for kw in ['gol', 'jugador', 'equipo', 'partido', 'barça', 'fc barcelona']):
            return 'nombres_propios'
        
        # Detectar expresiones catalanas
        if any(cat_word in word_lower for cat_word in ['visca', 'força', 'gràcies', 'barça']):
            return 'expresiones_catalan'
        
        # Por defecto, nombres propios
        return 'nombres_propios'
    
    def add_correction(self, original: str, corrected: str, category: str = 'correcciones_aprendidas'):
        """Añadir una corrección al diccionario"""
        if category not in self.dictionary:
            self.dictionary[category] = {}
        
        self.dictionary[category][original.lower()] = corrected
        self.save_dictionary()
        print(f"✓ Añadida corrección: '{original}' → '{corrected}' en categoría '{category}'")
