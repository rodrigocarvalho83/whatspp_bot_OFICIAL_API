# utils/sent_status.py
import os
import json
from datetime import datetime

CAMINHO_LOG = "contatos_enviados/status_log.json"

def _carregar_log():
    if not os.path.exists(CAMINHO_LOG):
        return {}
    with open(CAMINHO_LOG, encoding='utf-8') as f:
        return json.load(f)

def _salvar_log(log):
    with open(CAMINHO_LOG, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

def ja_enviado(codigo_pedido):
    log = _carregar_log()
    return str(codigo_pedido) in log

def marcar_como_enviado(codigo_pedido):
    log = _carregar_log()
    log[str(codigo_pedido)] = {
        "datahora": datetime.now().isoformat()
    }
    _salvar_log(log)

def registrar_log(numero, nome, status):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {numero} - {nome} => {status}")
