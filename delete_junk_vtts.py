import pymysql

DB_HOST = "193.203.168.198"
DB_NAME = "u214755203_zerffcb"
DB_USER = "u214755203_ss"
DB_PASS = "Sreg8888!!88hdb"
DB_PORT = 3306

connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, port=DB_PORT)

with connection.cursor() as cursor:
    cursor.execute("DELETE FROM transcriptions WHERE vtt = '[VTT_NOT_FOUND]'")
    connection.commit()
    print("Filas eliminadas:", cursor.rowcount)
connection.close()
