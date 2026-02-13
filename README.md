# Zerf Transcriptor - Sistema de Transcripción con Whisper

Sistema automatizado para transcribir videos de YouTube con Whisper.

## Uso

### Construir y ejecutar con Docker

```bash
# Construir la imagen
docker-compose build

# Procesar un video (modo manual)
docker-compose run --rm zerf-transcriptor

# Ver archivos generados
ls output/transcripciones/
ls output/sugerencias/
```

### Estructura de archivos generados

- `output/transcripciones/yyyymmdd [título].srt` - Subtítulos con timestamps
- `output/transcripciones/yyyymmdd [título].txt` - Texto plano
- `output/sugerencias/yyyymmdd [título]_sugerencias.json` - Sugerencias de mejora

### Configuración

Edita `docker-compose.yml` para cambiar:
- `WHISPER_MODEL`: modelo a usar (base, small, medium, large)
- `LANGUAGE`: idioma principal (es, ca, auto)
- `BATCH_SIZE`: videos por ejecución

### Diccionario personalizado

Edita `data/diccionario.json` para añadir nombres propios o expresiones.
