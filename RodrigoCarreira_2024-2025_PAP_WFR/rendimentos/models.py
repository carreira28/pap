from rendimentos.config import conectar_bd


def get_users(username):
        con = conectar_bd()
        cursor = con.cursor(dictionary=True)  
        cursor.execute('SELECT * FROM utilizadores WHERE utilizador = %s', (username,))
        user=cursor.fetchone()
        con.close()
        return user
