# utils/message_queue.py
import os
import requests
import json
import time
from utils.sent_status import registrar_log
from core.whatsapp_cloud import WhatsAppCloudAPI

FILA_PATH = "log/fila_mensagens.json"
ENTREGAS_PATH = "log/entregas_cloud_api.json"
BLACKLIST_PATH = "config/blacklist.json"
os.makedirs("log", exist_ok=True)
os.makedirs("config", exist_ok=True)

fila = []
cloud_api = WhatsAppCloudAPI()


def _extrair_template_do_item(item):
    """
    Aceita aliases para facilitar integração com payloads externos.
    Prioridade:
    - template_name (padrão interno)
    - template (dict ou string)
    - nome_template
    """
    template_name = item.get("template_name")
    template_params = item.get("template_params") or []
    template_lang = item.get("template_lang") or item.get("template_language") or "pt_BR"

    template_legacy = item.get("template")
    if not template_name and isinstance(template_legacy, str):
        template_name = template_legacy
    elif not template_name and isinstance(template_legacy, dict):
        template_name = template_legacy.get("name")
        template_params = template_legacy.get("params") or template_params
        template_lang = template_legacy.get("language") or template_lang

    if not template_name:
        template_name = item.get("nome_template")

    return template_name, template_params, template_lang

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

def registrar_entrega_aceita(numero, nome, resposta):
    registros = []
    if os.path.exists(ENTREGAS_PATH):
        try:
            with open(ENTREGAS_PATH, "r", encoding="utf-8") as f:
                registros = json.load(f)
        except json.JSONDecodeError:
            registros = []

    contatos = (resposta or {}).get("contacts") or [{}]
    mensagens = (resposta or {}).get("messages") or [{}]

    registros.append({
        "numero_informado": numero,
        "wa_id": contatos[0].get("wa_id"),
        "nome": nome,
        "message_id": mensagens[0].get("id"),
        "status": "accepted_by_cloud_api",
        "timestamp": time.time(),
    })

    with open(ENTREGAS_PATH, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)


def processar_fila(driver=None):
    global fila
    if not cloud_api.esta_configurado():
        print("❌ Cloud API não configurada. Fila não processada.")
        return
    
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
            template_name, template_params, template_lang = _extrair_template_do_item(item)
            
            if template_name:
                resposta = cloud_api.enviar_template(numero, template_name, template_params, template_lang)
            elif caminho_video and os.path.exists(caminho_video):
                resposta = cloud_api.enviar_midia(numero, caminho_video, mensagem)
                if mensagem and item.get("force_text_with_media"):
                    cloud_api.enviar_texto(numero, mensagem)
            else:
                resposta = cloud_api.enviar_texto(numero, mensagem)

            wa_id = ((resposta or {}).get("contacts") or [{}])[0].get("wa_id", "desconhecido")
            message_id = ((resposta or {}).get("messages") or [{}])[0].get("id", "sem-id")
            registrar_entrega_aceita(numero, nome, resposta)
            registrar_log(
                numero,
                nome,
                f"Mensagem aceita pela Cloud API (message_id={message_id}, wa_id={wa_id}). "
                "Entrega final depende do status no webhook da Meta.",
            )
            if wa_id != "desconhecido" and wa_id != numero:
                print(
                    f"⚠️ Número normalizado pela Meta: enviado={numero}, wa_id={wa_id}. "
                    "Verifique formatação no banco (DDI+DDD+número)."
                )
        except requests.HTTPError as e:
            detalhe = ""
            erro_code = None
            if e.response is not None:
                detalhe = f" | resposta={e.response.text}"
                try:
                    erro_json = e.response.json()
                    erro_code = (erro_json.get("error") or {}).get("code")
                except Exception:
                    pass

            if erro_code == 131047 and not template_name:
                fallback_template = item.get("fallback_template_name")
                fallback_params = item.get("fallback_template_params") or []
                if fallback_template:
                    try:
                        resposta = cloud_api.enviar_template(numero, fallback_template, fallback_params)
                        wa_id = ((resposta or {}).get("contacts") or [{}])[0].get("wa_id", "desconhecido")
                        message_id = ((resposta or {}).get("messages") or [{}])[0].get("id", "sem-id")
                        registrar_entrega_aceita(numero, nome, resposta)
                        registrar_log(
                            numero,
                            nome,
                            f"Template de reengajamento enviado (message_id={message_id}, wa_id={wa_id}, template={fallback_template}).",
                        )
                        continue
                    except Exception as template_error:
                        print(f"❌ Falha ao enviar template de reengajamento: {template_error}")

            print(f"❌ Erro HTTP ao processar item da fila: {e}{detalhe}")
            nova_fila.append(item)

        except Exception as e:
            print(f"❌ Erro ao processar item da fila: {e}")
            nova_fila.append(item)

        time.sleep(5)  # Pequeno intervalo entre mensagens

    fila = nova_fila
    salvar_fila()

# Expondo função para importação em outros módulos
__all__ = ["adicionar_na_fila", "processar_fila"]