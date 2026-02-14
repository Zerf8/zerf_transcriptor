
import json
import os
from src.transcriber import Transcriber
from src.dictionary_manager import DictionaryManager
from src.clip_analyzer import ClipAnalyzer
from src.correction_suggester import CorrectionSuggester

def reprocess_topocho():
    # Nombre exacto
    video_name = "20260128 FC BARCELONA 4 COPENHAGUE 1 GRAN LAMINE PARA REMONTAR  EL REAL MADRID FUERA DEL TOPOCHO"
    raw_path = f"output/transcripciones/raw/{video_name}_raw.json"
    
    if not os.path.exists(raw_path):
        print(f"❌ No encuentro RAW: {raw_path}")
        return

    print(f"🔄 Re-procesando: {video_name}")
    
    # Cargar RAW
    with open(raw_path, 'r', encoding='utf-8') as f:
        result = json.load(f)
        
    # Inicializar herramientas
    dict_manager = DictionaryManager() # Cargará el diccionario actualizado
    transcriber = Transcriber(model_name="medium", language="es") # Solo para utilidades
    clip_analyzer = ClipAnalyzer()
    
    # 1. Aplicar Diccionario (Fase 2: Post-procesado)
    print("📚 Aplicando correcciones...")
    text_corregido = dict_manager.apply_corrections(result['text'])
    
    segments_corregidos = []
    for segment in result['segments']:
        seg_copy = segment.copy()
        seg_copy['text'] = dict_manager.apply_corrections(segment['text'])
        segments_corregidos.append(seg_copy)
        
    # 2. Generar Archivos
    print("💾 Regenerando SRT y TXT...")
    srt_path = f"output/transcripciones/srt/{video_name}.srt"
    txt_path = f"output/transcripciones/txt/{video_name}.txt"
    transcriber.generate_srt(segments_corregidos, srt_path)
    transcriber.generate_txt(text_corregido, txt_path)
    
    # 3. Clips con Hashtags
    print("✂️  Regenerando Clips...")
    clips = clip_analyzer.analyze_segments(segments_corregidos)
    clips_path = f"output/clips/{video_name}_clips.json"
    clip_analyzer.save_clips_report(clips, clips_path)
    
    print("✅ ¡Listo! Versión Reprocesada.")

if __name__ == "__main__":
    reprocess_topocho()
