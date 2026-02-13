
"""
Generador de reportes Excel
Crea un resumen detallado de las transcripciones y clips
"""
import pandas as pd
import json
import os
from datetime import datetime
from typing import List, Dict

class ExcelReporter:
    def __init__(self, output_file: str = 'output/reporte_general.xlsx'):
        self.output_file = output_file
        
    def generate_report(self, state_file: str = 'data/processing_state.json'):
        """Generar Excel desde el estado actual"""
        if not os.path.exists(state_file):
            print("⚠️ No hay estado para generar reporte")
            return
            
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
            
        videos = state.get('videos_procesados', [])
        if not videos:
            print("⚠️ No hay videos procesados")
            return
            
        # 1. Preparar datos para Hoja RESUMEN
        summary_data = []
        all_clips = []
        
        for v in videos:
            meta = v.get('metadata', {})
            stats = v.get('execution_stats', {})
            
            # Datos Resumen
            summary_data.append({
                'Fecha Proceso': v.get('fecha_proceso', '')[:19].replace('T', ' '),
                'Video': meta.get('title', 'Sin título'),
                'Duración (s)': meta.get('duration', 0),
                'Duración (min)': round(meta.get('duration', 0) / 60, 2),
                'PC Procesado': stats.get('hostname', 'Desconocido'),
                'Tiempo Proceso (s)': round(stats.get('duration_seconds', 0), 2),
                'Ratio (x)': round(stats.get('duration_seconds', 0) / max(1, meta.get('duration', 0)), 2)
            })
            
            # Cargar Clips si existen
            clips_path = meta.get('clips_path', '')
            if clips_path and os.path.exists(clips_path):
                try:
                    with open(clips_path, 'r', encoding='utf-8') as f:
                        clips_json = json.load(f)
                        for clip in clips_json.get('suggested_clips', []):
                            all_clips.append({
                                'Video': meta.get('title', 'Sin título'),
                                'Minuto Inicio': clip.get('start_time', ''),
                                'Minuto Final': clip.get('end_time', ''),
                                'Etiquetas': " ".join(clip.get('tags', [])),
                                'Texto': clip.get('text_preview', clip.get('text', '')),
                                'Tipo': clip.get('reason', ''),
                                'Score': clip.get('score', 0)
                            })
                except Exception as e:
                    print(f"Error cargando clips de {clips_path}: {e}")

        # 2. Crear DataFrame y guardar Excel
        df_summary = pd.DataFrame(summary_data)
        df_clips = pd.DataFrame(all_clips)
        
        # Ordenar clips por Score descendente
        if not df_clips.empty:
            df_clips = df_clips.sort_values(by='Score', ascending=False)
        
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        
        try:
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                df_summary.to_excel(writer, sheet_name='Resumen Videos', index=False)
                df_clips.to_excel(writer, sheet_name='Clips Destacados', index=False)
                
                # Auto-ajustar columnas (básico, openpyxl lo hace mejor manual pero esto ayuda)
                # ... (lógica de formato podría ir aquí)
                
            print(f"📊 Reporte Excel generado: {self.output_file}")
        except Exception as e:
            print(f"❌ Error generando Excel: {e}")
