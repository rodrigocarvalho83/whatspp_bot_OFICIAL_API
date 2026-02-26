# utils/message_queue.py
import os
import json
import time
from utils.sent_status import registrar_log
from core.whatsapp import abrir_conversa, enviar_texto, enviar_midia

FILA_PATH = "log/fila_mensagens.json"
BLACKLIST_PATH = "config/blacklist.json"
os.makedirs("log", exist_ok=True)
os.makedirs("config", exist_ok=True)

fila = []

def carregar_blacklist():
    if not os.path.exists(BLACKLIST_PATH):
        return []
    try:
        with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def adicionar_na_fila(mensagem_dict):
    blacklist = carregar_blacklist()
    numero = mensagem_dict["numero"]

    if numero in blacklist:
        # Barrado pela blacklist
        log_msg = f"Número {numero} ({mensagem_dict['nome']}) barrado pela blacklist. Mensagem não enviada."
        print(f"🚫 {log_msg}")
        registrar_log(numero, mensagem_dict.get('nome', ''), "Mensagem barrada pela blacklist")
        return

    fila.append(mensagem_dict)
    with open(FILA_PATH, "w", encoding="utf-8") as f:
        json.dump(fila, f, ensure_ascii=False, indent=2)
    print(f"📥 Mensagem adicionada à fila para {mensagem_dict['numero']} ({mensagem_dict['nome']})")

def carregar_fila():
    if not os.path.exists(FILA_PATH):
        return []
    try:
        with open(FILA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def salvar_fila():
    with open(FILA_PATH, "w", encoding="utf-8") as f:
        json.dump(fila, f, ensure_ascii=False, indent=2)

def processar_fila(driver):
    global fila
    if not fila:
        fila = carregar_fila()

    if not fila:
        print("📭 Fila de mensagens vazia.")
        return

    print("📤 Processando fila de mensagens...")
    nova_fila = []

    for item in fila:
        try:
            numero = item["numero"]
            nome = item["nome"]
            mensagem = item["mensagem"]
            caminho_video = item.get("caminho_video")

            if abrir_conversa(driver, numero, mensagem):
                enviado = True
                if caminho_video and os.path.exists(caminho_video):
                    enviado = enviar_midia(driver, caminho_video)
                else:
                    enviado = enviar_texto(driver)

                if enviado:
                    registrar_log(numero, nome, "Mensagem enviada com sucesso")
                else:
                    registrar_log(numero, nome, "Falha ao enviar mensagem")
            else:
                registrar_log(numero, nome, "Número inválido no WhatsApp")
        except Exception as e:
            print(f"❌ Erro ao processar item da fila: {e}")
            nova_fila.append(item)

        time.sleep(25)  # Pequeno intervalo entre mensagens

    fila = nova_fila
    salvar_fila()

# Expondo função para importação em outros módulos
__all__ = ["adicionar_na_fila", "processar_fila"]