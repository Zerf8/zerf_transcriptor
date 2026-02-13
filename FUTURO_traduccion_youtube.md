# 🌍 Fase Futura: Traducción Multi-idioma y Subida Automática a YouTube

## Objetivo
Traducir automáticamente los subtítulos .srt a múltiples idiomas y subirlos directamente a YouTube.

---

## 1️⃣ Traducción de Subtítulos

### Herramientas Disponibles
- **Google Translate API** (de pago, pero muy precisa)
- **DeepL API** (mejor calidad, especialmente para catalán/español)
- **OpenAI GPT-4** (puede entender contexto futbolístico)

### Flujo de Traducción
```
archivo.srt (español) 
    → Mantener timestamps exactos
    → Traducir solo el texto
    → archivo_en.srt (inglés)
    → archivo_fr.srt (francés)
    → archivo_pt.srt (portugués)
    → archivo_ca.srt (catalán - si no está ya)
```

### Idiomas Sugeridos (según audiencia)
1. **Inglés** - Audiencia internacional
2. **Portugués** - Brasil (mucho seguimiento del Barça)
3. **Francés** - Francia
4. **Catalán** - Audiencia local (si no está ya)
5. **Árabe** - Norte de África

### Ventaja con Whisper
Ya tenemos los timestamps perfectos del .srt, solo hay que traducir el texto.

---

## 2️⃣ Subida Automática a YouTube

### YouTube Data API v3
YouTube permite subir subtítulos programáticamente:

```python
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Autenticación con OAuth 2.0
youtube = build('youtube', 'v3', credentials=credentials)

# Subir subtítulo
request = youtube.captions().insert(
    part="snippet",
    body={
        "snippet": {
            "videoId": "VUMNuQcfhmw",
            "language": "en",
            "name": "English (Auto-translated)"
        }
    },
    media_body=MediaFileUpload('archivo_en.srt')
)
response = request.execute()
```

### Proceso Completo

1. **Transcribir** (ya implementado) → `archivo.srt`
2. **Traducir** → `archivo_en.srt`, `archivo_pt.srt`, etc.
3. **Subir a YouTube**:
   - Autenticarse con tu cuenta
   - Asociar cada .srt traducido al video correspondiente
   - YouTube los añade como opciones de subtítulos

### Configuración Necesaria

**Una sola vez:**
1. Crear proyecto en Google Cloud Console
2. Habilitar YouTube Data API v3
3. Crear credenciales OAuth 2.0
4. Autorizar la aplicación desde tu cuenta de YouTube

**Después es automático:**
```bash
# Procesar + Traducir + Subir todo en un solo comando
docker-compose run --rm zerf-transcriptor --translate --upload
```

---

## 3️⃣ Implementación Propuesta

### Nuevos Archivos

**`src/translator.py`**
```python
class SubtitleTranslator:
    def translate_srt(self, input_srt, target_language):
        # Parsear SRT
        # Traducir solo texto, mantener timestamps
        # Guardar nuevo SRT
        
    def batch_translate(self, srt_file, languages=['en', 'pt', 'fr']):
        # Traducir a múltiples idiomas
```

**`src/youtube_uploader.py`**
```python
class YouTubeUploader:
    def authenticate(self):
        # OAuth 2.0
        
    def upload_subtitle(self, video_id, srt_file, language):
        # Subir subtítulo a video específico
        
    def upload_all_subtitles(self, video_id, srt_files):
        # Subir todos los idiomas de un video
```

### Modificar `main.py`

```python
# Después de generar SRT español
if args.translate:
    translator = SubtitleTranslator()
    translated_srt = translator.batch_translate(
        srt_path, 
        languages=['en', 'pt', 'fr', 'ca']
    )
    
    if args.upload:
        uploader = YouTubeUploader()
        uploader.authenticate()
        for lang, srt_file in translated_srt.items():
            uploader.upload_subtitle(video_id, srt_file, lang)
```

### Variables de Entorno

```yaml
# docker-compose.yml
environment:
  - TRANSLATE_ENABLED=true
  - TRANSLATE_LANGUAGES=en,pt,fr,ca
  - YOUTUBE_UPLOAD_ENABLED=true
  - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/google_oauth.json
```

---

## 4️⃣ Costos Estimados

### Traducción (por 1000 videos de ~15 min)
- **Google Translate**: ~$20-40 USD (depende del texto)
- **DeepL**: ~$25-50 USD (mejor calidad)
- **GPT-4**: ~$100-200 USD (contextual, más caro)

### YouTube API
- **GRATIS** - Sin costo por subir subtítulos

### Recomendación
Empezar con **Google Translate** (buen balance precio/calidad), y para videos importantes usar **DeepL** o **GPT-4**.

---

## 5️⃣ Flujo Completo Automatizado

```
1. Procesar video con Whisper (español)
   ↓
2. Generar archivo.srt + archivo.txt
   ↓
3. Traducir archivo.srt → [en, pt, fr, ca].srt
   ↓
4. Subir todos los .srt a YouTube automáticamente
   ↓
5. Tus videos tienen subtítulos en 5 idiomas ✅
```

**Tiempo total añadido por video:** ~30 segundos (traducción) + 10 segundos (subida)

---

## 6️⃣ Beneficios

✅ **Alcance internacional**: Gente de todo el mundo puede ver tus videos  
✅ **SEO mejorado**: YouTube indexa los subtítulos, más descubribilidad  
✅ **Accesibilidad**: Personas sordas o con problemas de audio  
✅ **Automatización total**: Set it and forget it  
✅ **Profesionalismo**: Canal con aspecto más completo  

---

## Próximos Pasos (Cuando estés listo)

1. [ ] Decidir qué servicio de traducción usar
2. [ ] Crear cuenta Google Cloud + Habilitar YouTube API
3. [ ] Implementar `translator.py`
4. [ ] Implementar `youtube_uploader.py`
5. [ ] Probar con 1-2 videos
6. [ ] Activar para procesamiento masivo

---

**Nota:** Esta funcionalidad se puede añadir SIN romper nada del sistema actual. Es completamente modular.
