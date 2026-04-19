import pymysql

DB_HOST = "193.203.168.198"
DB_NAME = "u214755203_zerffcb"
DB_USER = "u214755203_ss"
DB_PASS = "Sreg8888!!88hdb"
DB_PORT = 3306

connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, port=DB_PORT, cursorclass=pymysql.cursors.DictCursor)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT v.id 
        FROM videos v 
        LEFT JOIN transcriptions t ON v.id = t.video_id 
        WHERE t.id IS NULL OR t.vtt IS NULL OR TRIM(t.vtt) = ''
    """)
    missing = cursor.fetchall()

    print(f"Marcando {len(missing)} videos como '[VTT_NOT_FOUND]'...")

    for vid in missing:
        cursor.execute("""
            INSERT INTO transcriptions (video_id, vtt, language) 
            VALUES (%s, %s, 'es')
            ON DUPLICATE KEY UPDATE vtt = vtt
        """, (vid['id'], '[VTT_NOT_FOUND]'))
        
    connection.commit()
print("Terminado.")
connection.close()
