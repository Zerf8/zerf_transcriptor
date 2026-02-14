
import os
import json
import re
from src.comparer import TranscriptionComparer
from src.state_manager import StateManager
from dotenv import load_dotenv

def sanitize_text(text: str) -> str:
    """Eliminar emojis y caracteres no-ASCII para evitar errores en Windows"""
    return re.sub(r'[^\x00-\x7F]+', ' ', text)

def run_batch_comparison():
    load_dotenv()
    comparer = TranscriptionComparer()
    state_manager = StateManager()
    
    stats = state_manager.get_processing_stats()
    processed_videos = state_manager.state.get('videos_procesados', [])
    
    # Filtrar solo vídeos procesados hoy (14 de febrero de 2026)
    today = "2026-02-14"
    today_videos = [v for v in processed_videos if v.get('fecha_proceso', '').startswith(today)]
    
    print(f"SEARCHING: Encontrados {len(today_videos)} videos procesados hoy para comparar.")
    
    all_discrepancies = []
    
    os.makedirs("output/comparisons", exist_ok=True)
    
    for video in today_videos:
        video_id = video.get('url', '').split('v=')[-1]
        title = video['metadata'].get('title', 'video')
        txt_path = video['metadata'].get('txt_path')
        yt_subs_path = f"videos/{video_id}.es.srt"
        
        if not txt_path or not os.path.exists(txt_path):
            print(sanitize_text(f"WARNING: No se encuentra el TXT de Whisper para: {title}"))
            continue
            
        if not os.path.exists(yt_subs_path):
            print(sanitize_text(f"WARNING: No se encuentran los subs de YouTube para: {title} ({yt_subs_path})"))
            continue
            
        print(sanitize_text(f"DEBUG: Comparando: {title}..."))
        
        with open(txt_path, 'r', encoding='utf-8') as f:
            whisper_text = f.read()
            
        with open(yt_subs_path, 'r', encoding='utf-8') as f:
            # Una limpieza básica del SRT de YouTube para el prompt
            youtube_text = f.read()
            # Eliminar numeración de SRT y timestamps si es posible para ahorrar tokens
            import re
            youtube_text = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', '', youtube_text)
            youtube_text = re.sub(r'\n+', ' ', youtube_text).strip()

        discrepancies = comparer.compare(whisper_text, youtube_text)
        
        if discrepancies:
            print(f"   OK: Encontradas {len(discrepancies)} discrepancias.")
            for d in discrepancies:
                d['video_title'] = title
                d['video_id'] = video_id
                all_discrepancies.append(d)
        else:
            print(f"   - No se encontraron discrepancias relevantes.")

    # Guardar reporte final
    report_path = "output/comparisons/reporte_maestro_hoy.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(all_discrepancies, f, ensure_ascii=False, indent=2)
    
    print(f"\nDONE: Analisis completado. Reporte guardado en: {report_path}")
    print(f"TOTAL: Total de discrepancias encontradas: {len(all_discrepancies)}")

if __name__ == "__main__":
    run_batch_comparison()
