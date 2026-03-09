import pymysql
import os
import dotenv

dotenv.load_dotenv('/home/ubuntu/servidor/transcripciones/.env')

conn = pymysql.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASS'),
    database=os.getenv('DB_NAME'),
    port=int(os.getenv('DB_PORT', 3306)),
    connect_timeout=10,
    read_timeout=30,
    write_timeout=30
)

try:
    with conn.cursor() as cursor:
        print("Clearing fields...")
        affected_t = cursor.execute("""
            UPDATE transcriptions 
            SET whisper_srt=NULL, 
                temp_refinado_srt=NULL, 
                refinado_srt=NULL, 
                whisper_text=NULL, 
                gemini_text=NULL,
                srt_content=NULL,
                raw_json=NULL
        """)
        print(f"Cleared {affected_t} transcriptions.")
        
        print("Resetting statuses...")
        affected_v = cursor.execute("UPDATE videos SET status='pending'")
        print(f"Reset {affected_v} videos.")
        
    conn.commit()
    print("Commit successful.")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
