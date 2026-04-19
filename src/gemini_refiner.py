
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

        # --- PARSEO DE SEGURIDAD (BLINDAJE DE TIEMPOS) ---
        import re
        def parse_srt(text):
            blocks = []
            raw_blocks = re.split(r'\n\s*\n', text.strip())
            for rb in raw_blocks:
                lines = rb.strip().split('\n')
                if len(lines) >= 2:
                    idx = lines[0].strip()
                    # Buscar línea de tiempo
                    time_idx = 1 if '-->' in lines[1] else -1
                    if time_idx == -1: continue # No es un bloque válido
                    
                    time_line = lines[time_idx].strip()
                    content = " ".join(lines[time_idx+1:]).strip()
                    blocks.append({"index": idx, "time": time_line, "text": content})
            return blocks

        original_blocks = parse_srt(base_text)
        if not original_blocks:
            return base_text # Si no podemos parsear, devolvemos original

        # Preparamos el texto simplificado para Gemini (sin tiempos)
        blocks_payload = "\n".join([f"[{b['index']}] {b['text']}" for b in original_blocks])

        audio_file = None
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

        prompt = [
            f"""
            Eres el Editor Jefe de ZerfAnalitza, experto en transcripciones de alta precisión y lingüística culé. 
            Tu misión es corregir y refinar los bloques de texto que te proporciono {'basándote PRINCIPALMENTE en lo que ESCUCHAS en el audio' if audio_file else 'refinando el texto Whisper'}.
            
            CONTEXTO:
            - Metadatos del Vídeo: {match_context}
            - Diccionario: {json.dumps(dictionary.get('correcciones_aprendidas', {}) if dictionary else {})}
            - El hablante es Zerf (el Barbut), seguidor culé apasionado.
            
            REGLAS CRÍTICAS:
            1. FIDELIDAD FONÉTICA: Si oyes un nombre (ej. "Rashford"), mantén Rashford. No lo cambies por contexto Barça (ej. no pongas "Raphinha").
            2. FORMATO DE RESPUESTA: Recibirás bloques marcados como [Número] Texto. Debes responder con la corrección manteniendo el índice:
               [Número] Texto corregido
            3. NO AÑADAS COMENTARIOS: Responde ÚNICAMENTE con los bloques procesados.
            4. TÉRMINOS ZERFISTAS: "Hola Culerada, Hola Zerfistas", "Sed buenos", "Força Barça", "socis", "Joan" (portero).
            5. LIMPIEZA: Elimina muletillas absurdas pero mantén el tono informal y canalla de Zerf.
            """
        ]

        if audio_file:
            prompt.append(audio_file)
        
        prompt.append(f"BLOQUES A REFINAR:\n{blocks_payload}")

        try:
            response = self.model.generate_content(prompt)
            raw_response = response.text
            
            # Reconstrucción del SRT con tiempos protegidos
            refined_map = {}
            # Buscar patrones [ID] Texto...
            matches = re.findall(r'\[(\d+)\]\s*(.*)', raw_response)
            for m_idx, m_text in matches:
                refined_map[m_idx] = m_text.strip()

            final_srt = []
            for b in original_blocks:
                new_text = refined_map.get(b['index'], b['text'])
                final_srt.append(f"{b['index']}\n{b['time']}\n{new_text}\n")
            
            if audio_file:
                try: genai.delete_file(audio_file.name)
                except: pass

            return "\n".join(final_srt).strip()
        except Exception as e:
            print(f"⚠️ Error refinando texto con Gemini 2.5 Pro: {e}")
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
