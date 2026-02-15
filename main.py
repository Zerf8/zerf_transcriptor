#!/usr/bin/env python3
"""
Zerf Transcriptor - Sistema de Transcripción con Whisper
Script principal que orquesta todo el proceso
"""
import os
import sys
# from src.youtube_downloader import YouTubeDownloader
from src.transcriber import Transcriber
from src.dictionary_manager import DictionaryManager
from src.correction_suggester import CorrectionSuggester
from src.state_manager import StateManager
from src.clip_analyzer import ClipAnalyzer
import yt_dlp
from datetime import datetime
import re
import json
from src.gemini_refiner import GeminiRefiner
from src.notifier import send_telegram_message
from dotenv import load_dotenv


# Implementación INLINE garantizada para evitar caché de Docker
class YouTubeDownloader:
    def __init__(self, output_dir: str = 'videos'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def extract_metadata(self, url: str) -> dict:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': False}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            upload_date = info.get('upload_date', '')
            fecha = datetime.strptime(upload_date, '%Y%m%d') if upload_date else datetime.now()
            return {
                'title': info.get('title', 'Sin título'),
                'duration': info.get('duration', 0),
                'upload_date': fecha,
                'video_id': info.get('id', ''),
                'channel': info.get('uploader', '')
            }
    
    def sanitize_filename(self, title: str) -> str:
        # Eliminar acentos y caracteres especiales
        import unicodedata
        title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
        # Mantener solo letras, números, espacios y guiones
        clean = re.sub(r'[^\w\s-]', '', title)
        return clean[:100].strip()
    
    def format_output_name(self, metadata: dict) -> str:
        fecha_str = metadata['upload_date'].strftime('%Y%m%d')
        title_clean = self.sanitize_filename(metadata['title'])
        return f"{fecha_str} {title_clean}"
    
    def cleanup(self, file_path: str):
        if os.path.exists(file_path):
            os.remove(file_path)

    def download_video(self, url: str):
        print(f"📥 Descargando (AUDIO ONLY - SUBPROCESS): {url}")
        metadata = self.extract_metadata(url)
        if not metadata: return None
        
        video_id = metadata['video_id']
        final_path = os.path.join(self.output_dir, f"{video_id}.m4a")
        
        # Si ya existe, lo usamos directamente (Feature solicitada para pruebas rápidas)
        if os.path.exists(final_path):
            print(f"📂 Audio local encontrado: {final_path} (Saltando descarga)")
            # Necesitamos asegurar que metadata tenga duración correcta si no descargamos
            return (final_path, metadata)

        # Comando CLI directo: yt-dlp usando módulo python para evitar problemas de PATH
        # IMPORTANTE: Forzar ubicación de ffmpeg local
        ffmpeg_local = os.path.abspath('ffmpeg.exe')
        
        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--ffmpeg-location', ffmpeg_local,
            '-f', '251/140/bestaudio',  # Priorizar Opus (251) o M4A (140)
            '--extract-audio',
            '--audio-format', 'm4a',    # Convertir a m4a para estandarizar
            '--write-auto-sub',         # Descargar subtítulos automáticos
            '--sub-lang', 'es',         # Idioma español
            '--convert-subs', 'srt',    # Convertir a SRT para que sea más fácil leer (o VTT)
            '--force-overwrites',
            '-o', os.path.join(self.output_dir, f"{video_id}.%(ext)s"),
            url
        ]
        
        try:
            import subprocess
            subprocess.run(cmd, check=True)
            
            if os.path.exists(final_path):
                print(f"✓ Descargado: {metadata['title']} ({os.path.getsize(final_path)/1024/1024:.2f} MB)")
                return (final_path, metadata)
        except Exception as e:
            print(f"Error en subprocess: {e}")
            
        return None



def load_video_urls(file_path: str = 'lista_maestra_videos.txt'):
    """Cargar URLs desde el archivo de texto"""
    urls = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and '|' in line:
                # Formato: URL | TÍTULO
                url = line.split('|')[0].strip()
                urls.append(url)
    return urls


def process_video(url: str, 
                 downloader: YouTubeDownloader,
                 transcriber: Transcriber,
                 dict_manager: DictionaryManager,
                 suggester: CorrectionSuggester,
                 clip_analyzer: ClipAnalyzer,
                 state_manager: StateManager,
                 gemini_refiner: GeminiRefiner):
    """Procesar un solo video completo"""
    
    print("\n" + "="*80)
    print(f"🎬 PROCESANDO VIDEO")
    print("="*80)
    
    try:
        # 1. Descargar video y extraer metadata
        download_result = downloader.download_video(url)
        if not download_result:
            raise Exception("Error en descarga")
        
        audio_path, metadata = download_result
        output_name = downloader.format_output_name(metadata)
        
        duration_sec = metadata.get('duration', 0)
        mins = int(duration_sec // 60)
        secs = int(duration_sec % 60)
        print(f"⏱️  Duración del video: {mins}m {secs}s")
        
        # 2. Transcribir con Whisper (o cargar caché)
        # Asegurar directorios
        os.makedirs("output/transcripciones/srt", exist_ok=True)
        os.makedirs("output/transcripciones/txt", exist_ok=True)
        os.makedirs("output/transcripciones/raw", exist_ok=True)
        os.makedirs("output/transcripciones/youtube", exist_ok=True) # Para subs de YT

        raw_json_path = f"output/transcripciones/raw/{output_name}_raw.json"
        
        # ... logic to check cache ...
        result = None
        
        if os.path.exists(raw_json_path):
            print(f"\n📂 Encontrada transcripción previa (RAW): {raw_json_path}")
            try:
                with open(raw_json_path, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                print("   ✓ Cargada desde caché")
            except Exception as e:
                print(f"   ⚠️ Error cargando caché: {e}")
        
        if not result:
            print(f"\n📝 Transcribiendo con modelo {transcriber.model_name}...")
            result = transcriber.transcribe_audio(audio_path)
            if not result:
                raise Exception("Error en transcripción")
            
            # Guardar resultado crudo INMEDIATAMENTE
            import json
            with open(raw_json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False)
            print(f"💾 Transcripción cruda guardada en: {raw_json_path}")
            
         # 3. EJECUTAR POST-PROCESADO (Diccionario, Clips, Archivos, Gemini)
        run_post_processing(result, output_name, metadata, transcriber, dict_manager, suggester, clip_analyzer, gemini_refiner, audio_path)
        
        # 8. Marcar como procesado
        srt_path = f"output/transcripciones/srt/{output_name}.srt"
        txt_path = f"output/transcripciones/txt/{output_name}.txt"
        sugerencias_path = f"output/sugerencias/{output_name}_sugerencias.json"
        clips_path = f"output/clips/{output_name}_clips.json"
        
        state_manager.mark_processed(url, {
            'title': metadata['title'],
            'duration': metadata['duration'],
            'srt_path': srt_path,
            'txt_path': txt_path,
            'sugerencias_path': sugerencias_path,
            'clips_path': clips_path,
            'raw_path': raw_json_path
        })
        
        # 9. Limpiar archivo temporal
        if os.path.exists(audio_path):
            downloader.cleanup(audio_path)
        
        print("\n" + "="*80)
        print(f"✅ VIDEO PROCESADO EXITOSAMENTE")
        print(f"   📄 SRT: {srt_path}")
        print(f"   📄 TXT: {txt_path}")
        print(f"   💡 Sugerencias: {sugerencias_path}")
        print(f"   ✂️  Clips sugeridos: {clips_path}")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR PROCESANDO VIDEO: {e}")
        import traceback
        traceback.print_exc()
        state_manager.mark_failed(url, str(e))
        return False


def run_post_processing(result, output_name, metadata, transcriber, dict_manager, suggester, clip_analyzer, gemini_refiner=None, audio_path=None):
    """
    Fase 2: Aplicar correcciones, generar archivos y analizar clips.
    Esta función es re-ejecutable sin necesidad de transcribir de nuevo.
    """
    print(f"\n⚙️  INICIANDO POST-PROCESADO...")
    
    # 3. Aplicar diccionario personalizado
    print(f"📚 Aplicando diccionario personalizado...")
    text_original = result['text']
    text_corregido = dict_manager.apply_corrections(text_original)
    
    # También corregir cada segmento
    segments_corregidos = []
    for segment in result['segments']:
        segment_corregido = segment.copy()
        segment_corregido['text'] = dict_manager.apply_corrections(segment['text'])
        segments_corregidos.append(segment_corregido)
    
    # 4. Generar archivos SRT y TXT
    print(f"💾 Generando archivos de salida...")
    
    # Asegurar directorios (por si se ejecuta post-proceso aislado)
    os.makedirs("output/transcripciones/srt", exist_ok=True)
    os.makedirs("output/transcripciones/txt", exist_ok=True)

    srt_path = f"output/transcripciones/srt/{output_name}.srt"
    txt_path = f"output/transcripciones/txt/{output_name}.txt"
    
    transcriber.generate_srt(segments_corregidos, srt_path)
    transcriber.generate_txt(text_corregido, txt_path)

    # --- PASO 4 & 5: REFINADO Y CLIPS CON GEMINI ---
    if gemini_refiner and gemini_refiner.model:
        print(f"✨ Iniciando Refinado Inteligente con Gemini 3 Flash...")
        
        # Intentar cargar subs de YouTube para apoyo
        youtube_subs_path = f"videos/{metadata.get('video_id')}.es.srt"
        youtube_text = ""
        if os.path.exists(youtube_subs_path):
            try:
                with open(youtube_subs_path, 'r', encoding='utf-8') as f:
                    youtube_text = f.read()
                print("   ✓ Cargados subtítulos de YouTube para contexto")
                # Copiar a carpeta de transcripciones para tenerlo organizado
                import shutil
                shutil.copy(youtube_subs_path, f"output/transcripciones/youtube/{output_name}_yt.srt")
            except: pass

        # 4.1 Refinar texto
        text_refinado = gemini_refiner.refine_transcription(text_corregido, youtube_text, dict_manager.dictionary)
        txt_refinado_path = f"output/transcripciones/txt/{output_name}_refinado.txt"
        with open(txt_refinado_path, 'w', encoding='utf-8') as f:
            f.write(text_refinado)
        print(f"   ✓ Texto refinado guardado: {txt_refinado_path}")

        # 4.2 Analizar Emoción con Audio (Si tenemos audio_path)
        if audio_path and os.path.exists(audio_path):
            clips_ai = gemini_refiner.analyze_audio_emotion(audio_path, text_refinado)
            if clips_ai:
                print(f"   ✓ Gemini ha detectado {len(clips_ai)} clips basados en emoción!")
                # Guardar clips de IA
                clips_ai_path = f"output/clips/{output_name}_clips_ai.json"
                with open(clips_ai_path, 'w', encoding='utf-8') as f:
                    json.dump({"suggested_clips": clips_ai}, f, ensure_ascii=False, indent=2)
                
                # Opcional: Fusionar con los clips de reglas
                # (Por ahora los dejamos separados para que Zerf compare)

    # 5. Identificar palabras con baja confianza
    low_conf = transcriber.get_low_confidence_words(result['segments'])
    
    # 6. Generar sugerencias
    print(f"💡 Generando sugerencias de corrección...")
    suggestions = suggester.suggest_corrections(low_conf, text_original, metadata)
    sugerencias_path = f"output/sugerencias/{output_name}_sugerencias.json"
    suggester.generate_review_report(suggestions, metadata, sugerencias_path)

    # 7. Analizar CLIPS
    print(f"✂️  Analizando posibles clips...")
    suggested_clips = clip_analyzer.analyze_segments(segments_corregidos)
    clips_path = f"output/clips/{output_name}_clips.json"
    clip_analyzer.save_clips_report(suggested_clips, clips_path)
    
    print("✅ Post-procesado completado")


def main():
    """Función principal"""
    # Cargar variables de entorno
    load_dotenv()
    
    # Configuración desde variables de entorno
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'medium')
    LANGUAGE = os.getenv('LANGUAGE', 'es')
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '3'))
    REVIEW_MODE = os.getenv('REVIEW_MODE', 'auto')
    
    print("🚀 ZERF TRANSCRIPTOR")
    print(f"   Modelo Whisper: {WHISPER_MODEL}")
    print(f"   Idioma: {LANGUAGE}")
    print(f"   Modo: {REVIEW_MODE}")
    print(f"   Videos por lote: {BATCH_SIZE}")
    print("")
    
    # Inicializar componentes
    downloader = YouTubeDownloader()
    transcriber = Transcriber(model_name=WHISPER_MODEL, language=LANGUAGE)
    dict_manager = DictionaryManager()
    suggester = CorrectionSuggester()
    clip_analyzer = ClipAnalyzer()
    state_manager = StateManager()
    gemini_refiner = GeminiRefiner()
    
    # Cargar lista de videos

    
    # Cargar lista de URLs
    print("📋 Cargando lista de videos...")
    all_urls = load_video_urls()
    print(f"   Total de URLs en lista: {len(all_urls)}")
    
    # Filtrar URLs pendientes
    pending_urls = state_manager.get_pending_urls(all_urls)
    print(f"   URLs pendientes: {len(pending_urls)}")
    
    if not pending_urls:
        print("\n✨ ¡Todos los videos han sido procesados!")
        return
    
    # Procesar videos (limitado por BATCH_SIZE)
    videos_to_process = pending_urls[:BATCH_SIZE]
    
    print(f"\n📺 Procesando {len(videos_to_process)} video(s)...\n")
    
    for i, url in enumerate(videos_to_process, 1):
        print(f"\n{'#'*80}")
        print(f"VIDEO {i}/{len(videos_to_process)}")
        print(f"{'#'*80}\n")
        
        success = process_video(url, downloader, transcriber, dict_manager, suggester, clip_analyzer, state_manager, gemini_refiner)
        
        # En modo manual, pausar después de cada video
        if REVIEW_MODE == 'manual' and i < len(videos_to_process):
            # Generar Excel al momento para ver progreso
            try:
                from src.excel_reporter import ExcelReporter
                reporter = ExcelReporter()
                reporter.generate_report()
            except ImportError:
                pass
            
            print("\n" + "-"*80)
            print("📋 REVISIÓN MANUAL")
            print("   Por favor revisa:")
            print("   - Los archivos generados (.srt y .txt)")
            print("   - El archivo de sugerencias (_sugerencias.json)")
            print("   - El archivo Excel recién actualizado (reporte_general.xlsx)")
            print("   - Actualiza el diccionario si es necesario")
            print("-"*80)
            input("\nPresiona ENTER para continuar con el siguiente video...")
    
    # Generar reporte final Excel
    try:
        from src.excel_reporter import ExcelReporter
        reporter = ExcelReporter()
        reporter.generate_report()
    except Exception as e:
        print(f"Error generando Excel final: {e}")
    
    # Mostrar estadísticas finales
    stats = state_manager.get_processing_stats()
    print("\n" + "="*80)
    print("📊 ESTADÍSTICAS")
    print("="*80)
    print(f"   ✅ Videos procesados: {stats['total_procesados']}")
    print(f"   ❌ Videos fallidos: {stats['total_fallidos']}")
    print(f"   ⏳ Videos pendientes: {stats['total_pendientes']}")
    print("="*80)
    print("\n✨ Proceso completado\n")
    
    # Enviar aviso por Telegram
    msg = (
        f"🚀 *ZERF TRANSCRIPTOR*\n\n"
        f"✅ *Lote Finalizado*\n"
        f"📊 Procesados: {stats['total_procesados']}\n"
        f"❌ Fallidos: {stats['total_fallidos']}\n\n"
        f"¡Todo listo para revisar los resultados!"
    )
    send_telegram_message(msg)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}")
        sys.exit(1)
