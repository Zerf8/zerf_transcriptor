
import re
import unicodedata

def limpiar(texto):
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    texto = re.sub(r'[^\w\s-]', '', texto)
    texto = re.sub(r'[\s]+', '_', texto)
    return texto

t1 = "Video Con #Hashtag y Espacios"
print(f"Original: {t1}")
print(f"Limpio:   {limpiar(t1)}")
