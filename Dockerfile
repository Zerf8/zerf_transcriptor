# Usa Python 3.11 slim como base
FROM python:3.11-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    WHISPER_MODEL=medium

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Crear directorios de trabajo
WORKDIR /app
RUN mkdir -p /app/videos /app/output /app/data /app/src

# Copiar requirements primero (para aprovechar cache de Docker)
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY src/ /app/src/
COPY main.py /app/

# El comando por defecto ejecuta el script principal
CMD ["python", "main.py"]
