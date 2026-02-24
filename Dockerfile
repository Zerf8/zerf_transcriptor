FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar algunos paquetes y para FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar la caché de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir \
    faster-whisper \
    google-generativeai \
    python-dotenv \
    yt-dlp \
    sqlalchemy \
    pymysql \
    fastapi \
    uvicorn \
    google-auth-oauthlib \
    google-api-python-client \
    google-auth-httplib2

# Copiar el resto del código
COPY . .

# Exponer el puerto de la API
EXPOSE 8000

# Comando para ejecutar la API
CMD ["python", "-m", "uvicorn", "manager_api:app", "--host", "0.0.0.0", "--port", "8000"]
