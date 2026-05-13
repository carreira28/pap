import mysql.connector

def conectar_bd():
    return mysql.connector.connect(
    host="localhost",
    user="root",
    password="R1M2_v3c4",
    database="db_rcarreira"
    )