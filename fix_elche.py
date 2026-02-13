
import re

def fix_elche_transcription():
    # Rutas de archivos
    txt_path = "output/transcripciones/20260131 ELCHE 1 FC BARCELONA 3 VICTORIA FALLANDO DEMASIADO  LAMINE VUELVE A ESTAR A SU NIVEL.txt"
    srt_path = "output/transcripciones/20260131 ELCHE 1 FC BARCELONA 3 VICTORIA FALLANDO DEMASIADO  LAMINE VUELVE A ESTAR A SU NIVEL.srt"

    # Diccionario manual para este fix rápido
    corrections = {
        r"\bho la culerada de la zerfistas\b": "Hola Culerada. Hola Zerfistas.",
        r"\bhola culerada de la zerfistas\b": "Hola Culerada. Hola Zerfistas.",
        r"\bla fina\b": "Raphinha",
        r"\bbafete\b": "Albacete",
        r"\badductor\b": "aductor",
        r"\bmateo llaoz\b": "Mateu Lahoz",
        r"\bpeter la anguila\b": "Peter la Anguila", 
        r"\bkundé\b": "Kounde", # Quitar acento
        r"\bsurfista\b": "Zerfistas", 
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
        
        # También sobreescribir el original si quieres, o dejarlo así
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
    fix_elche_transcription()
