
import time
import re
from rapidfuzz import fuzz

def test_fuzzy_speed():
    # Texto de prueba (corto, unas 100 palabras)
    text = """
    Hola zerfistas, bienvenidos a otro vídeo. Hoy vamos a hablar de farran torres y de la miña mal.
    El partido contra la real sociedad fue un robo, qué vergüenza. El árbitro mateo llaoz es un desastre.
    kundé estuvo espectacular en defensa. ansu fati necesita mejorar.
    jajaja me parto con lo que dijo xavi. puta mierda de arbitraje.
    visca el barça y visca catalunya. feran tores jugó bien pero le falta gol.
    """ * 10  # Repetimos 10 veces para simular un minuto de texto (~1000 palabras)

    dictionary = {
        "ferran": "Ferran",
        "lamine yamal": "Lamine Yamal",
        "kounde": "Koundé",
        "mateu lahoz": "Mateu Lahoz",
        "real sociedad": "Real Sociedad",
        "zerfistas": "Zerfistas"
    }

    print(f"Texto de prueba: {len(text)} caracteres, aprox {len(text.split())} palabras.")
    print("-" * 50)

    # 1. Prueba REGEX (Baseline)
    start_time = time.time()
    corrected_regex = text
    for wrong, correct in dictionary.items():
        pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
        corrected_regex = pattern.sub(correct, corrected_regex)
    regex_time = time.time() - start_time
    print(f"Time Regex: {regex_time:.4f} s")

    # 2. Prueba FUZZY (La lenta)
    start_time = time.time()
    corrected_fuzzy = text
    words = corrected_fuzzy.split()
    new_words = []
    i = 0
    while i < len(words):
        word = words[i]
        # Bigrams
        bigram = " ".join(words[i:i+2]) if i + 1 < len(words) else ""
        replaced = False
        
        # Bigram check
        if bigram:
            for wrong, correct in dictionary.items():
                if abs(len(bigram) - len(wrong)) > 3: continue
                ratio = fuzz.ratio(bigram.lower(), wrong.lower())
                if ratio > 85:
                    new_words.append(correct)
                    i += 2  # ¡Avanzamos 2 palabras!
                    replaced = True
                    break
            if replaced: continue  
            # Aquí 'continue' es seguro porque 'i' ha avanzado dentro del if

        # Word check
        for wrong, correct in dictionary.items():
            if abs(len(word) - len(wrong)) > 2: continue
            ratio = fuzz.ratio(word.lower(), wrong.lower())
            if ratio > 88:
                new_words.append(correct)
                i += 1  # ¡Avanzamos 1 palabra!
                replaced = True
                break
        
        if not replaced:
            new_words.append(word)
            i += 1
            
    corrected_fuzzy = " ".join(new_words)
    fuzzy_time = time.time() - start_time
    print(f"Time Fuzzy: {fuzzy_time:.4f} s")
    print(f"Factor de ralentización: {fuzzy_time / regex_time:.1f}x")

if __name__ == "__main__":
    test_fuzzy_speed()
