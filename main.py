#!/usr/bin/env python3
"""
Zerf Transcriptor - Sistema de Transcripción con Whisper
Script principal que orquesta todo el proceso
"""
import os
import sys
from src.youtube_downloader import YouTubeDownloader
from src.transcriber import Transcriber
from src.dictionary_manager import DictionaryManager
from src.correction_suggester import CorrectionSuggester
from src.state_manager import StateManager


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
                 state_manager: StateManager):
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
        
        # 2. Transcribir con Whisper
        print(f"\n📝 Transcribiendo...")
        result = transcriber.transcribe_audio(audio_path)
        if not result:
            raise Exception("Error en transcripción")
        
        # 3. Aplicar diccionario personalizado
        print(f"\n📚 Aplicando diccionario personalizado...")
        text_original = result['text']
        text_corregido = dict_manager.apply_corrections(text_original)
        
        # También corregir cada segmento
        segments_corregidos = []
        for segment in result['segments']:
            segment_corregido = segment.copy()
            segment_corregido['text'] = dict_manager.apply_corrections(segment['text'])
            segments_corregidos.append(segment_corregido)
        
        # 4. Generar archivos SRT y TXT
        print(f"\n💾 Generando archivos de salida...")
        srt_path = f"output/transcripciones/{output_name}.srt"
        txt_path = f"output/transcripciones/{output_name}.txt"
        
        transcriber.generate_srt(segments_corregidos, srt_path)
        transcriber.generate_txt(text_corregido, txt_path)
        
        # 5. Identificar palabras con baja confianza
        print(f"\n🔍 Analizando confianza...")
        low_conf = transcriber.get_low_confidence_words(result['segments'])
        
        # 6. Generar sugerencias
        print(f"\n💡 Generando sugerencias...")
        suggestions = suggester.suggest_corrections(low_conf, text_original, metadata)
        
        # Guardar reporte de sugerencias
        sugerencias_path = f"output/sugerencias/{output_name}_sugerencias.json"
        suggester.generate_review_report(suggestions, metadata, sugerencias_path)
        
        # 7. Marcar como procesado
        state_manager.mark_processed(url, {
            'title': metadata['title'],
            'duration': metadata['duration'],
            'srt_path': srt_path,
            'txt_path': txt_path,
            'sugerencias_path': sugerencias_path
        })
        
        # 8. Limpiar archivo temporal
        downloader.cleanup(audio_path)
        
        print("\n" + "="*80)
        print(f"✅ VIDEO PROCESADO EXITOSAMENTE")
        print(f"   📄 SRT: {srt_path}")
        print(f"   📄 TXT: {txt_path}")
        print(f"   💡 Sugerencias: {sugerencias_path}")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR PROCESANDO VIDEO: {e}")
        state_manager.mark_failed(url, str(e))
        return False


def main():
    """Función principal"""
    
    # Configuración desde variables de entorno
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'medium')
    LANGUAGE = os.getenv('LANGUAGE', 'es')
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '1'))
    REVIEW_MODE = os.getenv('REVIEW_MODE', 'manual')
    
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
    state_manager = StateManager()
    
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
        
        success = process_video(url, downloader, transcriber, dict_manager, suggester, state_manager)
        
        # En modo manual, pausar después de cada video
        if REVIEW_MODE == 'manual' and i < len(videos_to_process):
            print("\n" + "-"*80)
            print("📋 REVISIÓN MANUAL")
            print("   Por favor revisa:")
            print("   - Los archivos generados (.srt y .txt)")
            print("   - El archivo de sugerencias (_sugerencias.json)")
            print("   - Actualiza el diccionario si es necesario")
            print("-"*80)
            input("\nPresiona ENTER para continuar con el siguiente video...")
    
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


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}")
        sys.exit(1)
