### core/database.py
import fdb

def executar_consulta(sql):
    conn = fdb.connect(
        host='localhost',
        database='C:/Users/rodri/AppData/Local/RAL Tecnologia/CreateInstall/CONSUMER.FDB',
        user='SYSDBA',
        password='masterkey'
    )
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchall()