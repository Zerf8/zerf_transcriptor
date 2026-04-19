
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
            self.model = genai.GenerativeModel('gemini-2.5-pro')
        else:
            self.model = None

    def refine_transcription(self, base_text: str, support_text: str = "", dictionary: Dict = None, audio_path: str = None, match_context: str = "") -> str:
        """Paso 4: Refinar el texto respetando los bloques originales (Karaoke)"""
        if not self.model:
            return base_text # Fallback al original

        if audio_path and os.path.exists(audio_path):
            try:
                print(f"🧠 Escuchando audio para refinamiento experto: {os.path.basename(audio_path)}")
                audio_file = genai.upload_file(path=audio_path)
                # Esperar a que se procese
                while audio_file.state.name == "PROCESSING":
                    time.sleep(2)
                    audio_file = genai.get_file(audio_file.name)
            except Exception as e:
                print(f"⚠️ Error subiendo audio: {e}")
                return "" # Retornar vacío para indicar fallo en modo estricto

        prompt = [
            f"""
            Eres el Editor Jefe de ZerfAnalitza, experto en transcripciones de alta precisión y lingüística culé. 
            Tu misión es crear una transcripción DEFINITIVA del vídeo basándote PRINCIPALMENTE en lo que ESCUCHAS en el audio.
            
            CONTEXTO:
            - Metadatos del Vídeo (Título/Desc): {match_context}
            - Diccionario de correcciones: {json.dumps(dictionary.get('correcciones_aprendidas', {}) if dictionary else {})}
            - El hablante es Zerf (el Barbut), seguidor apasionado del FC Barcelona.
            
            REGLAS DE ORO:
            1. EL AUDIO MANDA: Si la transcripción de apoyo (Whisper) dice algo fonéticamente parecido a un nombre propio (ej. "La Fina") pero tú escuchas el nombre real o lo ves en el Título (ej. "Raphinha"), CORRIGE sin dudar.
            2. MANTÉN LA ESTRUCTURA: Devuelve exactamente el mismo número de bloques que la entrada. No fusiones bloques.
            3. LIMPIEZA: Elimina muletillas excesivas o alucinaciones (como "suscríbete" en momentos de silencio), pero mantén el tono apasionado, vulgar e informal de Zerf.
            4. TÉRMINOS ZERFISTAS: "Hola culerada, hola zerfistas", "Sed buenos", "Força Barça", "Joan" (portero), "Lamine", "Xavi", etc.
            5. FORMATO: Responde ÚNICAMENTE con el contenido refinado en formato SRT/VTT (el mismo que la entrada).
            """
        ]

        if audio_file:
            prompt.append(audio_file)
        
        prompt.append(f"TRANSCRIPCIÓN BASE (Estructura a seguir):\n{base_text}")
        if support_text:
            prompt.append(f"TEXTO SUCIO DE APOYO (Whisper):\n{support_text[:5000]}")

        try:
            response = self.model.generate_content(prompt)
            refined_text = response.text
            
            # Limpiar respuesta de markdown
            if "```" in refined_text:
                for tag in ["```srt", "```vtt", "```"]:
                    if tag in refined_text:
                        refined_text = refined_text.split(tag)[1].split("```")[0]
                        break
            
            if audio_file:
                try: genai.delete_file(audio_file.name)
                except: pass

            return refined_text.strip()
        except Exception as e:
            print(f"⚠️ Error refinando texto con Gemini 2.5 Pro: {e}")
            if audio_file:
                try: genai.delete_file(audio_file.name)
                except: pass
            return ""
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
