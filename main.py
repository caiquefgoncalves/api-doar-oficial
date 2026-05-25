from flask import Flask, send_from_directory, jsonify, request, make_response
from flask_cors import CORS
import os
from datetime import datetime

app = Flask(__name__)


CORS(app,
     origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://192.168.0.135:5173", "10.92.3.167", "10.92.3.158", "10.92.3.152"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
     supports_credentials=True
     )



@app.before_request
def handle_options():
    if request.method == 'OPTIONS':
        response = make_response()
        origin = request.headers.get('Origin', '*')
        allowed_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://192.168.0.135:5173",
            "http://10.92.3.137:5173",
            "http://10.92.3.137:5000",
            "*"
        ]
        if origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Access-Control-Allow-Credentials'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response, 200


app.config.from_pyfile('config.py')

host = app.config['DB_HOST']
database = app.config['DB_NAME']
user = app.config['DB_USER']
password = app.config['DB_PASSWORD']

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'Usuarios'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'Projetos'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'Atualizacoes'), exist_ok=True)

print(f"UPLOAD_FOLDER: {app.config['UPLOAD_FOLDER']}")


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

from funcao import decodificar_token, enviando_email, gerar_token
from db import conexao


from usuario import *
from projeto import *
from ongs import *
from atualizacao import *
from comentarios import *
from graficos_relatorio import *


if __name__ == '__main__':
    print("\n=== ROTAS REGISTRADAS ===")
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/static'):
            print(f"{list(rule.methods)} {rule.rule}")
    print("=========================\n")
    app.run(host='0.0.0.0', port=5000, debug=True)