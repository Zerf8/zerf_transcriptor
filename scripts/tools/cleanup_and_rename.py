
import os
import re
import unicodedata

def clean_filename(name):
    """Limpia el nombre de archivo (elimina acentos y caracteres raros)"""
    # Normalizar unicode (quitar acentos)
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Quitar extensiones temporales para limpiar el nombre base
    name = name.replace('_corregido_final', '').replace('_corregido', '')
    # Quitar extensiones reales para procesar base
    base, ext = os.path.splitext(name)
    # Limpiar base
    clean_base = re.sub(r'[^\w\s-]', '', base).strip()
    return f"{clean_base}{ext}"

def reorganize_files():
    base_dir = "output/transcripciones"
    subdirs = ["txt", "srt"]
    
    print("🧹 Iniciando limpieza y renombrado...")

    for subdir in subdirs:
        current_dir = os.path.join(base_dir, subdir)
        if not os.path.exists(current_dir): continue
        
        files = os.listdir(current_dir)
        
        # Agrupar por "nombre base aproximado" para detectar versiones _corregido
        # Mapa: nombre_base_limpio -> lista de archivos reales
        file_map = {}
        
        for f in files:
            clean_name = clean_filename(f)
            if clean_name not in file_map:
                file_map[clean_name] = []
            file_map[clean_name].append(f)
            
        # Procesar grupos
        for clean_name, original_files in file_map.items():
            if not original_files: continue

            # Ordenar por prioridad: _corregido_final (3) > _corregido (2) > normal (1)
            original_files.sort(key=lambda x: (
                3 if '_corregido_final' in x else
                2 if '_corregido' in x else
                1
            ), reverse=True)
            
            best_original = original_files[0]
            target_path = os.path.join(current_dir, clean_name)
            source_path = os.path.join(current_dir, best_original)
            
            # 1. Borrar TODAS las versiones obsoletas (que no son la mejor)
            for bad_file in original_files[1:]:
                bad_path = os.path.join(current_dir, bad_file)
                if bad_file != clean_name: # No borrar si casualmente el "malo" ya tiene el nombre destino (lo sobreescribiremos luego)
                    try:
                        print(f"🗑️  Borrando obsoleto: {bad_file}")
                        os.remove(bad_path)
                    except OSError:
                        pass

            # 2. Renombrar la mejor versión al nombre limpio final
            if best_original != clean_name:
                print(f"✅ Renombrando: {best_original} -> {clean_name}")
                # Si existe el destino (que podría ser uno de los "malos" que acabamos de borrar o no), borrarlo para asegurar
                if os.path.exists(target_path):
                     try:
                        os.remove(target_path)
                     except OSError:
                        pass
                try:
                    os.rename(source_path, target_path)
                except OSError as e:
                    print(f"Error renombrando {best_original}: {e}")
            else:
                 print(f"🆗 Ya limpio: {clean_name}")

if __name__ == "__main__":
    reorganize_files()
