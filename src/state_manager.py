"""
Gestor de estado de procesamiento
Rastrea qué videos han sido procesados, cuáles han fallado y el progreso general
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional


class StateManager:
    def __init__(self, state_file: str = 'data/processing_state.json'):
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Cargar estado desde archivo JSON"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'videos_procesados': [],
            'videos_fallidos': [],
            'ultimo_procesado': None,
            'estadisticas': {
                'total_procesados': 0,
                'total_fallidos': 0,
                'total_pendientes': 0
            }
        }
    
    def save_state(self):
        """Guardar estado a archivo JSON"""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
    
    def mark_processed(self, url: str, metadata: Dict):
        """Marcar un video como procesado exitosamente"""
        entry = {
            'url': url,
            'fecha_proceso': datetime.now().isoformat(),
            'metadata': metadata
        }
        self.state['videos_procesados'].append(entry)
        self.state['ultimo_procesado'] = url
        self.state['estadisticas']['total_procesados'] += 1
        self.save_state()
    
    def mark_failed(self, url: str, error: str):
        """Marcar un video como fallido"""
        entry = {
            'url': url,
            'fecha_intento': datetime.now().isoformat(),
            'error': error
        }
        self.state['videos_fallidos'].append(entry)
        self.state['estadisticas']['total_fallidos'] += 1
        self.save_state()
    
    def is_processed(self, url: str) -> bool:
        """Verificar si un video ya fue procesado"""
        processed_urls = [v['url'] for v in self.state['videos_procesados']]
        return url in processed_urls
    
    def get_pending_urls(self, all_urls: List[str]) -> List[str]:
        """Obtener URLs pendientes de procesar"""
        processed_urls = set(v['url'] for v in self.state['videos_procesados'])
        pending = [url for url in all_urls if url not in processed_urls]
        self.state['estadisticas']['total_pendientes'] = len(pending)
        return pending
    
    def get_processing_stats(self) -> Dict:
        """Obtener estadísticas de procesamiento"""
        return self.state['estadisticas'].copy()
