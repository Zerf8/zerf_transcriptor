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
    print("CONNECTION_SUCCESS")
    conn.close()
except Exception as e:
    print("CONNECTION_ERROR")
    print(str(e))
