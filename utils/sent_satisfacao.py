### utils/sent_satisfacao.py
import os
from datetime import datetime

BASE_DIR = 'contatos_enviados'
LOG_FILE = 'satisfacao_log.txt'
os.makedirs(BASE_DIR, exist_ok=True)

def ja_enviado(telefone):
    caminho = os.path.join(BASE_DIR, 'satisfacao.txt')
    if not os.path.exists(caminho):
        return False
    with open(caminho, 'r') as f:
        return telefone in {linha.strip() for linha in f}

def marcar_como_enviado(telefone):
    caminho = os.path.join(BASE_DIR, 'satisfacao.txt')
    with open(caminho, 'a') as f:
        f.write(f'{telefone}\n')

def registrar_log(telefone, nome, status):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f'[{now}] {telefone} - {nome} - {status}\n')

