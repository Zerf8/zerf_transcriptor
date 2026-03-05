# Zerf Transcriptor - Sistema de Transcripción con Whisper

Sistema automatizado para transcribir videos de YouTube con Whisper, gestionarlo mediante una base de datos interactiva en Hostinger y conectar automatizaciones con Telegram.

**Dashboard Live:** [Zerf Subtitle Manager](https://siverus-linkerman2.hostingersite.com/)

---

## 📂 Estructura del Proyecto

El proyecto está diseñado para ser modular y separar el panel web, del motor de inteligencia artificial y de los pequeños scripts de mantenimiento:

*   **`/src`**: Código fuente principal. Contiene la conexión y estructuración de la Base de Datos (`models.py`) y las notificaciones (`notify_telegram.py`).
*   **`manager_api.py` / `manager_dashboard.html`**: El panel de control visual para revisar y editar los subtítulos y los metadatos sincronizados de YouTube.
*   **`gestionar_subtitulos.py`**: Motor principal para manipular, renombrar y ordenar archivos `.srt`.
*   **`script_transcription_local.py / _google_colab.py`**: El corazón del transcriptor. Descargan audio, transcriben con *Whisper* y refinan textos usando *Gemini*.
*   **`/scripts`**: Utilidades y automatizaciones, categorizados por uso:
    *   `/database`: Sincronizan el canal de YouTube con MySQL (`sync_channel_to_mysql.py`, `update_youtube_metadata.py`) y gestionan migraciones/reordenaciones.
    *   `/drive`: Scripts para autorizar, escanear y sincronizar subtítulos con Google Drive.
    *   `/tools`: Herramientas sueltas de limpieza, diagnóstico y pruebas de regex.
*   **`/data`**: Archivos estáticos como el `diccionario.json` (usado por Gemini para autocorregir nombres de jugadores).
*   **`/docs`**, **`/logs`**, **`/bin`**: Documentación adicional, registros de ejecución y binarios pesados (como *FFmpeg*).

---

## 🚀 Uso Rápido (Docker)

El sistema está preparado para ejecutarse de forma aislada mediante Docker, lo que evita problemas de configuración local:

```bash
# Construir la imagen
docker-compose build

# Levantar el entorno (Dashboard API + DB Local opcional)
docker-compose up -d

# Procesar un video (modo manual interactivo)
docker-compose run --rm zerf-transcriptor
```

### Configuración de Entorno `.env`
El proyecto depende de un archivo `.env` en la raíz (ver `.env.example`). Parámetros clave:
*   `GOOGLE_API_KEY`: Necesario tanto para el motor de *Gemini AI* como para extraer metadatos de la API de *YouTube Data v3*.
*   Configuración de Hostinger (`DB_HOST`, `DB_NAME`, `DB_USER`...): Hacia dónde envía la API los resultados finales y metadatos.
*   `TELEGRAM_BOT_TOKEN`: Usado para alertar al administrador de transcripciones acabadas o errores críticos.

## 📝 Salidas Generadas

1.  **Archivos Locales:**
    *   `output/transcripciones/*.srt` - Subtítulos con timestamps.
    *   `output/transcripciones/*.txt` - Texto plano.
2.  **Base de Datos en Producción:**
    *   La tabla `videos` de Hostinger se auto-nutre de metadatos (fechas, views, covers) y de JSONs enteros de todo el contenido del vídeo para montar vistas en la web.
