import sys
import os

# Add root project path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models import get_engine
from sqlalchemy import text

def add_columns():
    engine = get_engine()
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE transcriptions ADD COLUMN translated_title TEXT;"))
            print("Columna translated_title añadida.")
        except Exception as e:
            print(f"La columna translated_title probablemente ya existe: {e}")
            
        try:
            conn.execute(text("ALTER TABLE transcriptions ADD COLUMN translated_description TEXT;"))
            print("Columna translated_description añadida.")
        except Exception as e:
            print(f"La columna translated_description probablemente ya existe: {e}")
            
        conn.commit()
    print("Migración completada.")

if __name__ == '__main__':
    add_columns()
