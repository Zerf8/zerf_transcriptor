import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("DB_HOST")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASS")
db = os.getenv("DB_NAME")
port = int(os.getenv("DB_PORT", 3306))

try:
    conn = pymysql.connect(host=host, user=user, password=password, database=db, port=port, connect_timeout=10)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    cursor.execute("SELECT COUNT(*) as total FROM videos")
    total_videos = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM transcriptions WHERE srt_content IS NOT NULL AND srt_content != ''")
    trans_with_content = cursor.fetchone()['total']
    
    print(f"TOTAL_VIDEOS: {total_videos}")
    print(f"TRANS_WITH_CONTENT: {trans_with_content}")
    
    # Ver los IDs de los últimos 5 para comparar
    cursor.execute("SELECT youtube_id FROM videos ORDER BY upload_date DESC LIMIT 5")
    recent = cursor.fetchall()
    print(f"RECENT_IDS: {[r['youtube_id'] for r in recent]}")
    
    conn.close()
except Exception as e:
    print(f"ERROR: {e}")
