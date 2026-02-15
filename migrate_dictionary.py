import json
import os
from src.models import DictionaryEntry, get_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

JSON_FILE = r"c:\proyectos\Zerf_Transcriptor\data\diccionario.json"

def migrate_dict():
    if not os.path.exists(JSON_FILE):
        print("❌ No se encontró diccionario.json")
        return

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        engine = get_engine()
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Limpiar tabla previa
        session.execute(text("TRUNCATE TABLE dictionary"))
        session.commit()
        
        count = 0
        
        # Iterar sobre categorías (top-level keys)
        for category, items in data.items():
            if not isinstance(items, dict): continue
            
            for term, value in items.items():
                # Normalizar valor (correction)
                correction = value
                if isinstance(value, list):
                    correction = value[0] if value else term
                
                # Crear entrada
                # term = key (lo que buscamos/reemplazamos o el concepto)
                # correction = la forma correcta
                
                # Evitar duplicados de term
                exists = session.query(DictionaryEntry).filter_by(term=term).first()
                if not exists:
                    d = DictionaryEntry(
                        term=term,
                        correction=correction,
                        category=category
                    )
                    session.add(d)
                    count += 1

        session.commit()
        print(f"✅ Migrados {count} términos al diccionario.")
        session.close()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error migrando diccionario: {e}")

if __name__ == "__main__":
    migrate_dict()
