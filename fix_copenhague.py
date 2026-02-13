
import re

def fix_copenhague_transcription():
    # Rutas de archivos (Copenhague 29/01)
    txt_path = "output/transcripciones/20260129 ÉL DÍA DESPUÉS DEL PARTIDO ANTE EL COPENHAGUE  ANÁLISIS DE LAS JUGADAS CLAVE.txt"
    srt_path = "output/transcripciones/20260129 ÉL DÍA DESPUÉS DEL PARTIDO ANTE EL COPENHAGUE  ANÁLISIS DE LAS JUGADAS CLAVE.srt"

    # Diccionario manual para este fix rápido
    corrections = {
        r"\bho la culerada de la zerfistas\b": "Hola Culerada. Hola Zerfistas.",
        r"\bhola culeradas, hola, surfistas\b": "Hola Culerada. Hola Zerfistas.",
        r"\bhola culeradas\b": "Hola Culerada",
        r"\bsurfistas\b": "Zerfistas",
        r"\bLa Mink\b": "Lamine",
        r"\bla Mink\b": "Lamine",
        r"\bla Min\b": "Lamine",
        r"\bLa Min\b": "Lamine",
        r"\bMateo Llaoz\b": "Mateu Lahoz",
        r"\bkundé\b": "Kounde",
        r"\bhendrik larson\b": "Henrik Larsson",
        r"\bcubasi\b": "Cubarsí",
        r"\bpatreons\b": "Patreons",
        r"\bpatrón\b": "Patreon",
        r"\bchamps\b": "Champions",
        r"\bchampios\b": "Champions",
        r"\bchampes\b": "Champions",
        r"\bredneck\b": "redneck", # Está bien
    }

    print(f"Reparando: {txt_path} ...")

    # 1. Corregir TXT
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        fixed_content = content
        for wrong_regex, correct in corrections.items():
            fixed_content = re.sub(wrong_regex, correct, fixed_content, flags=re.IGNORECASE)

        with open(txt_path.replace('.txt', '_corregido_final.txt'), 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        # Sobreescribir original para que quede limpio
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
            
        print("✅ TXT corregido.")
    except FileNotFoundError:
        print("❌ No encontrado TXT")

    # 2. Corregir SRT
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        fixed_content = content
        for wrong_regex, correct in corrections.items():
            fixed_content = re.sub(wrong_regex, correct, fixed_content, flags=re.IGNORECASE)

        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
            
        print("✅ SRT corregido.")
    except FileNotFoundError:
        print("❌ No encontrado SRT")

if __name__ == "__main__":
    fix_copenhague_transcription()
