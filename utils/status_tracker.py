# modules/status_tracker.py
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "..", "log")
os.makedirs(LOG_DIR, exist_ok=True)
CAMINHO_LOG = os.path.join(LOG_DIR, "status_tracker.json")

def carregar_status_anteriores():
    if not os.path.exists(CAMINHO_LOG):
        print("📄 Arquivo de status não encontrado. Inicializando com registros atuais.")
        return None  # Sinaliza que é a primeira execução
    try:
        with open(CAMINHO_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def salvar_status_atuais(status_atuais):
    if not status_atuais:
        print("⚠️ Nenhum novo status para salvar.")
        return

    status_existente = carregar_status_anteriores()
    if status_existente is None:
        status_existente = {}  # Primeira execução: cria do zero

    status_existente.update(status_atuais)

    with open(CAMINHO_LOG, "w", encoding="utf-8") as f:
        json.dump(status_existente, f, ensure_ascii=False, indent=2)

    print(f"📝 {len(status_atuais)} novos status salvos em {CAMINHO_LOG}")

def status_mudou(chave_status, status_atual, status_anteriores):
    if status_anteriores is None:
        return True  # Primeira execução: tudo mudou
    return status_anteriores.get(chave_status) != status_atual