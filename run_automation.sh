#!/bin/bash
# Master Automation Script for Zerf Transcriptor

# 1. Asegurar que estamos en el directorio correcto
cd /home/ubuntu/servidor/transcripciones/zerf_transcriptor

# 2. Configurar el entorno
export PYTHONPATH=$PYTHONPATH:.
export PATH=$PATH:/home/ubuntu/.deno/bin

# 3. Sincronizar nuevos vídeos desde YouTube a la DB
echo "🔄 Sincronizando vídeos desde YouTube..."
python3 scripts/database/sync_youtube_to_db.py

# 4. Procesar todos los vídeos pendientes
echo "🚀 Iniciando procesamiento de vídeos pendientes..."
python3 main.py

echo "✅ Proceso de automatización finalizado."
