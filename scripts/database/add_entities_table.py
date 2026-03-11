"""
Este script crea las tablas 'entities' y 'video_entities' en la base de datos si no existen.
'entities' se utiliza para almacenar entidades reconocidas, y 'video_entities' es una tabla
de asociación para relacionar entidades con videos específicos.
"""
import os
import sys
from sqlalchemy import text, inspect
from dotenv import load_dotenv

# Añadir el directorio raíz al path para poder importar src.models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.models import get_engine, Base, video_entities, Entity

def update_db():
    engine = get_engine()
    inspector = inspect(engine)
    
    print("🔍 Comprobando tablas nuevas...")
    
    # Comprobar si las tablas ya existen
    existing_tables = inspector.get_table_names()
    
    try:
        if 'entities' not in existing_tables:
            print("🚀 Creando tabla 'entities'...")
            Entity.__table__.create(engine)
            print("✅ Tabla 'entities' creada.")
        else:
            print("ℹ️ La tabla 'entities' ya existe.")
            
        if 'video_entities' not in existing_tables:
            print("🚀 Creando tabla de asociación 'video_entities'...")
            video_entities.create(engine)
            print("✅ Tabla 'video_entities' creada.")
        else:
            print("ℹ️ La tabla 'video_entities' ya existe.")
            
        print("\n✨ Migración completada con éxito.")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")

if __name__ == "__main__":
    update_db()
