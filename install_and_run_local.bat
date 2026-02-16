@echo off
chcp 65001 > nul
echo ==========================================
echo    INSTALADOR Y EJECUTOR ZERF TRANSCRIPTOR
echo ==========================================
echo.
echo Detectando entorno...

:: Comprobar si Python está instalado
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no encontrado. Instala Python y añádelo al PATH.
    pause
    exit /b
)

echo.
echo 1. Instalando/Actualizando Dependencias (CUDA 12.1)...
echo Esto puede tardar un poco la primera vez.
echo.

:: Instalar PyTorch con soporte CUDA (Ajustado para 12.1 que es estable actualmente)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

:: Instalar OpenAI Whisper oficial
pip install git+https://github.com/openai/whisper.git --upgrade

:: Instalar yt-dlp y otras utilidades
pip install yt-dlp pandas

echo.
echo ==========================================
echo    DEPENDENCIAS INSTALADAS
echo ==========================================
echo.
echo Ejecutando script de transcripción...
echo.

python script_transcription_local.py

pause
