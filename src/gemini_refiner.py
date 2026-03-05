
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
            self.model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            self.model = None

    def refine_transcription(self, base_text: str, support_text: str = "", dictionary: Dict = None, audio_path: str = None) -> str:
        """Paso 4: Refinar el texto respetando los bloques originales (Karaoke)"""
        if not self.model:
            return base_text # Fallback al original

        audio_file = None
        if audio_path and os.path.exists(audio_path):
            try:
                print(f"🧠 Subiendo audio para refinamiento multimodal...")
                audio_file = genai.upload_file(path=audio_path)
                # Esperar a que se procese
                while audio_file.state.name == "PROCESSING":
                    time.sleep(2)
                    audio_file = genai.get_file(audio_file.name)
            except Exception as e:
                print(f"⚠️ Error subiendo audio para refinamiento: {e}")

        prompt = [
            f"""
            Eres el editor jefe de 'ZerfAnalitza'. Tu misión es limpiar y dar formato profesional a esta transcripción.
            
            REGLAS:
            1. Usa el diccionario de correcciones: {json.dumps(dictionary.get('correcciones_aprendidas', {}) if dictionary else {})}
            2. MANTÉN ESTRICTAMENTE EL MISMO NÚMERO DE BLOQUES. No unas bloques ni los acortes. Cada bloque de tiempo debe tener su texto correspondiente.
            3. SIEMPRE mantén el estilo del 'Barbut' (coloquial, apasionado, culé).
            4. FORMATO: Devuelve EXACTAMENTE el mismo formato que la entrada (SRT o VTT). Mantiene los mismos timestamps milisegundo a milisegundo. No inventes despedidas. Si un bloque parece una alucinación (como "suscríbete" repetido en silencio), límpialo pero NO elimines el bloque de tiempo.
            5. Responde ÚNICAMENTE con el contenido refinado (SRT o VTT).
            """
        ]

        if audio_file:
            prompt.append(audio_file)
        
        prompt.append(f"CONTENIDO ORIGINAL (ESTRUCTURA DE BLOQUES A REFINAR):\n{base_text[:20000]}")
        prompt.append(f"TEXTO APOYO:\n{support_text[:10000] if support_text else 'No disponible'}")

        try:
            response = self.model.generate_content(prompt)
            refined_text = response.text
            
            # Limpiar respuesta (quitar bloques de código si Gemini los pone)
            if "```" in refined_text:
                if "```srt" in refined_text:
                    refined_text = refined_text.split("```srt")[1].split("```")[0]
                elif "```" in refined_text:
                    refined_text = refined_text.split("```")[1].split("```")[0]
            
            return refined_text.strip()
        except Exception as e:
            print(f"⚠️ Error refinando texto con Gemini: {e}")
            if audio_file:
                try: genai.delete_file(audio_file.name)
                except: pass
            return base_text

    def analyze_audio_emotion(self, audio_path: str, transcript_text: str) -> List[Dict]:
        """Paso 5: Analizar clips basados en el AUDIO real (emoción y risas)"""
        if not self.model or not os.path.exists(audio_path):
            return []

        print(f"🧠 Subiendo audio a Gemini para análisis emocional (incluyendo risas): {os.path.basename(audio_path)}...")
        
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
                3. MOMENTOS DE RISA O CACHONDEO (Carcajadas, momentos de humor, ironía divertida).
                4. MOMENTOS DE TRISTEZA/DECEPCIÓN (Voz quebrada, silencios, hablando de lesiones).
                
                Para cada clip detectado dame:
                - start_time: (en formato HH:MM:SS)
                - end_time: (en formato HH:MM:SS)
                - score: (1-10 de intensidad)
                - reason: (Breve descripción de la emoción o risa detectada en el tono de voz)
                - tags: (Hashtags sugeridos como #ira, #pasion, #risa, #BARCELONA)
                
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
