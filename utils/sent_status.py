# utils/sent_status.py
import os
import json
from datetime import datetime

CAMINHO_LOG = "contatos_enviados/status_log.json"

def _carregar_log():
    if not os.path.exists(CAMINHO_LOG):
        return {}
    try:
        with open(CAMINHO_LOG, encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Se o JSON estiver corrompido, evita quebrar os módulos.
        # Mantém cópia para diagnóstico e recria o log limpo.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_backup = f"{CAMINHO_LOG}.corrompido_{timestamp}"
        try:
            os.replace(CAMINHO_LOG, caminho_backup)
            print(f"⚠️ status_log.json corrompido. Backup salvo em: {caminho_backup}")
        except Exception:
            pass
        return {}
    except Exception:
        return {}

def _salvar_log(log):
    os.makedirs(os.path.dirname(CAMINHO_LOG), exist_ok=True)
    caminho_tmp = f"{CAMINHO_LOG}.tmp"
    with open(caminho_tmp, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    # Escrita atômica para evitar arquivo parcial em interrupções.
    os.replace(caminho_tmp, CAMINHO_LOG)

def ja_enviado(codigo_pedido, saldo=None):
    log = _carregar_log()
    chave = f"{codigo_pedido}_{saldo}" if saldo is not None else str(codigo_pedido)
    return chave in log

def marcar_como_enviado(codigo_pedido, saldo=None):
    log = _carregar_log()
    chave = f"{codigo_pedido}_{saldo}" if saldo is not None else str(codigo_pedido)
    log[chave] = {
        "datahora": datetime.now().isoformat()
    }
    _salvar_log(log)

def registrar_log(numero, nome, status):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {numero} - {nome} => {status}")
