"""
Este script audita la base de datos para encontrar videos que no tienen 
un archivo VTT asociado o que tienen VTTs vacíos. También identifica los VTTs
que están explícitamente marcados en inglés ('Language: en').
"""
import os
import pymysql
import logging
import re
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(message)s')
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = int(os.getenv("DB_PORT", 3306))

def audit_vtts_exact():
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Videos sin VTT
            query_missing = """
                SELECT v.id, v.youtube_id, v.title 
                FROM videos v 
                LEFT JOIN transcriptions t ON v.id = t.video_id 
                WHERE t.id IS NULL OR t.vtt IS NULL OR TRIM(t.vtt) = ''
            """
            cursor.execute(query_missing)
            missing_vtts = cursor.fetchall()

            # Extraemos todos los VTT
            cursor.execute("SELECT t.id, t.video_id, v.youtube_id, v.title, t.vtt FROM transcriptions t JOIN videos v ON t.video_id = v.id WHERE t.vtt IS NOT NULL AND TRIM(t.vtt) != ''")
            vtt_records = cursor.fetchall()
            
            english_vtts = []
            
            for row in vtt_records:
                vtt_text = row['vtt']
                
                # Buscamos la etiqueta formal de 'Language: en' al inicio del archivo (primeros 500 chars)
                header = vtt_text[:500].lower()
                if re.search(r'language:\s*en', header):
                    english_vtts.append(row)

            print("=" * 50)
            print(f"RESULTADOS AUDITORÍA EXACTA (Basada en Metadatos)")
            print("=" * 50)
            print(f"Total de VTTs evaluados en BD: {len(vtt_records)}")
            print(f"Total VTT Faltantes: {len(missing_vtts)}")
            print(f"VTTs explícitamente marcados como INGLÉS (Language: en): {len(english_vtts)}")
            print("=" * 50)
            
            if english_vtts:
                print("Lista de VTTs en INGLÉS:")
                for m in english_vtts:
                    print(f"  - [{m['youtube_id']}] {m['title']}")
                    
    finally:
        connection.close()

if __name__ == "__main__":
    audit_vtts_exact()
