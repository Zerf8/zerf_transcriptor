import sys
import os

# Add root project path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models import get_engine
from sqlalchemy import text

def add_column():
    engine = get_engine()
    with engine.connect() as conn:
        try:
            # Check if column exists first (MySQL)
            result = conn.execute(text("SHOW COLUMNS FROM videos LIKE 'metadata_updated_at';"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE videos ADD COLUMN metadata_updated_at DATETIME NULL;"))
                print("✓ Columna metadata_updated_at añadida con éxito.")
            else:
                print("ℹ La columna metadata_updated_at ya existe.")
            conn.commit()
        except Exception as e:
            print(f"❌ Error durante la migración: {e}")

if __name__ == '__main__':
    add_column()
