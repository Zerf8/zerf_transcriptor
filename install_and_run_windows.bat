@echo off
setlocal
title Zerf Transcriptor - Instalador y Ejecutor Automatico

echo ===================================================
echo   ZERF TRANSCRIPTOR - AUTO SETUP PARA WINDOWS
echo ===================================================

:: 1. Comprobar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no encontrado. Por favor instala Python 3.10+ y marca "Add to PATH".
    echo Descarga: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 2. Crear entorno virtual si no existe
if not exist "venv" (
    echo [INFO] Creando entorno virtual Python (venv)...
    python -m venv venv
)

:: 3. Activar e instalar dependencias
echo [INFO] Verificando dependencias...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 4. Comprobar FFmpeg
if not exist "ffmpeg.exe" (
    echo [WARN] ffmpeg.exe no encontrado en la carpeta del proyecto.
    echo [INFO] Intentando descargar ffmpeg automaticamente...
    python -c "import urllib.request; import zipfile; import os; url='https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'; print('Descargando FFmpeg...'); urllib.request.urlretrieve(url, 'ffmpeg.zip'); print('Descomprimiendo...'); with zipfile.ZipFile('ffmpeg.zip', 'r') as zip_ref: zip_ref.extractall('temp_ffmpeg'); import shutil; src=os.path.join('temp_ffmpeg', 'ffmpeg-master-latest-win64-gpl', 'bin', 'ffmpeg.exe'); shutil.move(src, 'ffmpeg.exe'); shutil.rmtree('temp_ffmpeg'); os.remove('ffmpeg.zip'); print('FFmpeg instalado correctamente.')"
)

echo ===================================================
echo   TODO LISTO. EJECUTANDO TRANSCRIPTOR...
echo ===================================================
echo.

:: 5. Ejecutar script principal
python main.py

pause
