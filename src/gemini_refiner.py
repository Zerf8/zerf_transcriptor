
import os
import json
import time
import google.generativeai as genai
from typing import List, Dict, Optional

class GeminiRefiner:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-3-flash-preview')
        else:
            self.model = None

    def refine_transcription(self, whisper_text: str, youtube_text: str = "", dictionary: Dict = None) -> str:
        """Paso 4: Refinar el texto usando contexto de Whisper, YT y Diccionario"""
        if not self.model:
            return whisper_text # Fallback al original

        prompt = f"""
        Eres el editor jefe de 'ZerfAnalitza'. Tu misión es limpiar y dar formato profesional a esta transcripción.
        
        REGLAS:
        1. Usa el diccionario de correcciones: {json.dumps(dictionary.get('correcciones_aprendidas', {}) if dictionary else {})}
        2. Une frases, pon comas y puntos. El texto original es un flujo de voz, cámbialo a párrafos legibles.
        3. SIEMPRE mantén el estilo del 'Barbut' (coloquial, apasionado, culé). No lo hagas sonar como un robot.
        4. FILTRADO DE INTRO: Ignora la música de la intro y los cánticos iniciales. Whisper suele confundir la canción del inicio ("Barça, Barça, Barça") con palabras como "Pasa, pasa, pasa". ELIMINA esas repeticiones iniciales y empieza el texto directamente con tu saludo o el tema del vídeo.
        5. Si Whisper y YouTube dicen cosas distintas sobre un nombre de jugador, usa tu conocimiento futbolístico para decidir.
        6. Devuelve SOLO el texto limpio.

        TEXTO WHISPER:
        {whisper_text[:15000]}
        
        TEXTO APOYO (YOUTUBE):
        {youtube_text[:10000] if youtube_text else "No disponible"}
        """

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"⚠️ Error refinando texto con Gemini: {e}")
            return whisper_text

    def analyze_audio_emotion(self, audio_path: str, transcript_text: str) -> List[Dict]:
        """Paso 5: Analizar clips basados en el AUDIO real (emoción)"""
        if not self.model or not os.path.exists(audio_path):
            return []

        print(f"🧠 Subiendo audio a Gemini para análisis emocional: {os.path.basename(audio_path)}...")
        
        try:
            # Subir archivo a la API de Google
            audio_file = genai.upload_file(path=audio_path)
            
            # Esperar a que se procese
            while audio_file.state.name == "PROCESSING":
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)

            prompt = [
                audio_file,
                f"""
                Analiza el audio de este vídeo de ZerfAnalitza. 
                Zerf es el que habla (el Barbut). Quiero que detectes momentos Clave para YouTube Shorts basándote en su VOZ y EMOCIÓN.
                
                Busca específicamente:
                1. MOMENTOS DE IRA (Gritos, tono alto, insultos a árbitros).
                2. MOMENTOS DE PASIÓN/GOZO (Evolución de un gol, entusiasmo por Lamine Yamal).
                3. MOMENTOS DE TRISTEZA/DECEPCIÓN (Voz quebrada, silencios, hablando de lesiones).
                
                Para cada clip detectado dame:
                - start_time: (en formato HH:MM:SS)
                - end_time: (en formato HH:MM:SS)
                - score: (1-10 de intensidad)
                - reason: (Breve descripción de la emoción detectada en el tono de voz)
                - tags: (Hashtags sugeridos como #ira, #pasion, #BARCELONA)
                
                La duración de cada clip debe ser entre 15 y 59 segundos.
                IMPORTANTE: Responde ÚNICAMENTE con un objeto JSON que contenga una lista llamada 'suggested_clips'.
                """
            ]

            response = self.model.generate_content(prompt)
            
            # Limpiar respuesta JSON
            content = response.text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            # Eliminar el archivo de la nube de Google tras el análisis
            genai.delete_file(audio_file.name)
            
            return json.loads(content).get('suggested_clips', [])

        except Exception as e:
            print(f"⚠️ Error en análisis multimodal: {e}")
            return []
