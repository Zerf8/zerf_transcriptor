
import os
import json
import google.generativeai as genai
import re
from typing import List, Dict, Optional

class TranscriptionComparer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-3-flash-preview')
        else:
            self.model = None

    def compare(self, whisper_text: str, youtube_text: str) -> List[Dict]:
        """
        Compara la transcripción de Whisper con la de YouTube.
        Retorna una lista de discrepancias encontradas (nombres, términos técnicos).
        """
        if not self.model:
            print("WARNING: Modelo Gemini no configurado para comparación")
            return []

        prompt = f"""
        Eres un experto en periodismo deportivo y analista de datos del FC Barcelona. 
        Tu tarea es comparar dos transcripciones del mismo audio (una de Whisper y otra de YouTube) para encontrar errores en nombres propios, lugares y términos técnicos.

        REGLAS DE ANÁLISIS:
        1. Busca discrepancias en nombres de jugadores (ej. "Lamine", "Szczesny", "Cubarsí").
        2. Busca discrepancias en nombres de equipos o lugares (ej. "Montjuïc", "Athletic", "Brujas").
        3. Busca términos técnicos de fútbol o expresiones del canal (ej. "isquios", "pubalgia", "Culerada").
        4. Si ambos cometieron un error pero puedes deducir el término correcto, inclúyelo.
        
        FORMATO DE SALIDA:
        Devuelve ÚNICAMENTE un objeto JSON con una lista llamada 'discrepancias'. Cada elemento debe tener:
        - "termino_whisper": Lo que escribió Whisper.
        - "termino_youtube": Lo que escribió YouTube.
        - "correccion_propuesta": El término real correcto.
        - "categoria": (Nombre, Lugar, Termino Técnico, etc.)
        - "razon": Por qué crees que es ese término.

        TEXTO WHISPER:
        {whisper_text[:12000]}

        TEXTO YOUTUBE:
        {youtube_text[:12000]}
        """

        try:
            response = self.model.generate_content(prompt)
            content = response.text
            
            # Limpiar respuesta JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            data = json.loads(content)
            return data.get('discrepancias', [])
        except Exception as e:
            print(f"ERROR: Error comparando transcripciones con Gemini: {e}")
            return []
