from flask import Flask
import os
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Chave secreta para a sessão Flask
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10) # Expira em 10 minutos

from rendimentos import routes