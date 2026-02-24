import os, re, pymysql
from dotenv import load_dotenv

load_dotenv()

DIR_SRT = os.path.join('data', 'subtitles', 'SRT_YouTube')
srt_files = [f for f in os.listdir(DIR_SRT) if f.endswith('.srt')]

def ext_id(filename):
    name = os.path.splitext(filename)[0]
    if name.endswith('.es'):
        name = name[:-3]
    
    match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', name)
    if match: return match.group(1)
        
    if len(name) == 11: return name
        
    match = re.search(r'_([a-zA-Z0-9_-]{11})$', name)
    if match: return match.group(1)
        
    if len(name) > 11: return name[-11:]
    return name

ids_extracted = {f: ext_id(f) for f in srt_files}
unique_ids = list(set(ids_extracted.values()))

c = pymysql.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASS'),
    database=os.getenv('DB_NAME')
)
cr = c.cursor()

# Get all valid IDs from DB
cr.execute("SELECT id FROM videos")
db_ids_tuple = cr.fetchall()
db_ids = set(row[0] for row in db_ids_tuple)
c.close()

matched = []
unmatched = []

for filename, video_id in ids_extracted.items():
    if video_id in db_ids:
        matched.append((filename, video_id))
    else:
        unmatched.append((filename, video_id))

print(f"Total archivos SRT: {len(srt_files)}")
print(f"IDs que SI existen en BD: {len(matched)}")
print(f"IDs que NO existen en BD: {len(unmatched)}")
print("-" * 40)
print("Ejemplos de archivos NO ENCONTRADOS en BD (Nombre -> ID Extraído):")
for f, vid in unmatched[:20]:
    print(f"  {f} -> {vid}")
print("-" * 40)
print("Verificación cruzada completa.")
