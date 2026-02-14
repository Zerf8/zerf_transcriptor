
import os
import sys
import subprocess
import json

def generate_short_rant():
    # Configuración
    video_id = "gojSI0TGZJQ" 
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Clip de ENFADO "Cabrones dan el Madrid"
    start_time = "00:00:55"
    end_time = "00:01:25"
    output_name = "madrid_rant_short_v3"
    output_dir = "output/shorts"
    
    os.makedirs(output_dir, exist_ok=True)
    temp_video = os.path.join(output_dir, f"{output_name}_temp.mp4")
    final_video = os.path.join(output_dir, f"{output_name}.mp4") # Video final
    
    # 1. Descargar (si no existe)
    ffmpeg_local = os.path.abspath('ffmpeg.exe')
    if not os.path.exists(temp_video):
        print(f"📥 Descargando fragmento: {start_time}-{end_time}")
        cmd_download = [
            sys.executable, '-m', 'yt_dlp',
            '--ffmpeg-location', ffmpeg_local,
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--download-sections', f"*{start_time}-{end_time}",
            '--force-overwrites',
            '-o', temp_video,
            video_url
        ]
        try:
            subprocess.run(cmd_download, check=True)
        except:
            print("❌ Error descarga")
            return

    # 2. Generar Subtítulos Karaoke (SRT dinámico)
    raw_path = f"output/transcripciones/raw/20260128 FC BARCELONA 4 COPENHAGUE 1 GRAN LAMINE PARA REMONTAR  EL REAL MADRID FUERA DEL TOPOCHO_raw.json"
    temp_srt = os.path.join(output_dir, f"{output_name}_karaoke.srt")
    
    if os.path.exists(raw_path):
        print("📖 Creando Karaoke desde RAW...")
        create_karaoke_srt(raw_path, start_time, end_time, temp_srt)
    else:
        print("⚠️ RAW no encontrado. Usando SRT estándar.")
        srt_path = raw_path.replace('_raw.json', '.srt').replace('/raw/', '/srt/')
        create_simple_srt(srt_path, start_time, end_time, temp_srt)

    # 3. Componer Video Vertical
    print(f"✂️  Renderizando Vertical 9:16 + Blur + Subs...")
    
    # Path escapado para ffmpeg
    srt_filter_path = temp_srt.replace('\\', '/').replace(':', '\\:')
    
    # Estilo Subtítulos: ROJO, Borde Blanco, Fuente grande 24 (Más agresivo para RANT)
    # PrimaryColour=&H000000FF (ROJO en BGR: Blue=00, Green=00, Red=FF -> Rojo)
    style = "Alignment=2,Fontsize=24,PrimaryColour=&H000000FF,OutlineColour=&H00FFFFFF,BorderStyle=1,Outline=2,MarginV=60,Bold=1"

    # Filtro de video:
    filter_complex = (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale=-2:1280,crop=720:1280,boxblur=20:10[bg_blurred];"
        f"[fg]scale=720:-1[fg_scaled];"
        f"[bg_blurred][fg_scaled]overlay=0:(H-h)/2[v_mixed];"
        f"[v_mixed]subtitles='{srt_filter_path}':force_style='{style}'[v_out]"
    )
    
    cmd_convert = [
        ffmpeg_local, '-y',
        '-i', temp_video,
        '-filter_complex', filter_complex,
        '-map', '[v_out]', '-map', '0:a',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k',
        final_video
    ]
    
    subprocess.run(cmd_convert, check=True)
    print(f"✅ VIDEO LISTO: {final_video}")


def create_karaoke_srt(json_path, start_str, end_str, output_srt):
    import json
    def to_sec(t):
        p = t.replace(',', '.').split(':')
        return float(p[0])*3600 + float(p[1])*60 + float(p[2])
    def sec_str(s):
        m, sec = divmod(s, 60)
        h, m = divmod(m, 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{ms:03d}"

    start_clip = to_sec(start_str)
    end_clip = to_sec(end_str)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    words = []
    if 'segments' in data:
        for s in data['segments']:
            if 'words' in s: words.extend(s['words'])
    
    lines = []
    counter = 1
    buffer = []
    buffer_start = None
    
    # Agrupar de 3 en 3 palabras (Rápido para enfado)
    for w in words:
        if w['end'] < start_clip or w['start'] > end_clip: continue
        
        rel_start = max(0, w['start'] - start_clip)
        rel_end = w['end'] - start_clip
        
        if not buffer: buffer_start = rel_start
        buffer.append(w['word'].strip())
        
        if len(buffer) >= 3: # Max 3 palabras (más rápido)
            lines.append(f"{counter}\n{sec_str(buffer_start)} --> {sec_str(rel_end)}\n{' '.join(buffer)}\n")
            counter += 1
            buffer = []
            buffer_start = None
            
    if buffer and buffer_start is not None:
        lines.append(f"{counter}\n{sec_str(buffer_start)} --> {sec_str(rel_end)}\n{' '.join(buffer)}\n")

    with open(output_srt, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

def create_simple_srt(original_srt, start_str, end_str, output_srt):
    pass 

if __name__ == "__main__":
    generate_short_rant()
