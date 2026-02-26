# modules/clube_fimdesemana.py
from datetime import datetime, timedelta, time
from core.database import executar_consulta
from utils.formatters import formatar_nome, validar_numero
from utils.message_queue import adicionar_na_fila
from utils.sent_status import marcar_como_enviado
import os
import json
import urllib.parse

CAMINHO_JSON = "contatos_enviados/vip_fds.json"
IMAGEM_MIMO = "videos/promocoes/guarana1_5l.png"

ultima_execucao = datetime.min
intervalo_execucao = timedelta(minutes=1)

# Utilitário para carregar registros já enviados
def carregar_json():
    if not os.path.exists(CAMINHO_JSON):
        return {}
    try:
        with open(CAMINHO_JSON, encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

# Utilitário para salvar novo estado do JSON
def salvar_json(dados):
    with open(CAMINHO_JSON, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

# Verifica se estamos exatamente às 17:50 de sexta-feira
def hoje_sexta_promocao():
    agora = datetime.now()
    return agora.weekday() == 4 and agora.strftime("%H:%M") == "17:50"

# Verifica se uma data está no fim de semana anterior (sexta/sábado/domingo)
def fimdesemana_passado(data_pedido):
    hoje = datetime.today()
    inicio_fds = hoje - timedelta(days=hoje.weekday() + 3)  # sexta passada
    fim_fds = inicio_fds + timedelta(days=2)  # domingo passado
    return inicio_fds.date() <= data_pedido.date() <= fim_fds.date()

def should_run():
    global ultima_execucao
    agora = datetime.now()
    if agora - ultima_execucao >= intervalo_execucao:
        ultima_execucao = agora
        return True
    return False

def run(driver):
    if not should_run():
        return

    registros_enviados = carregar_json()
    novos_registros = registros_enviados.copy()

    sql = """
    SELECT
        FIRST 1000 p.FONEPRINCIPAL,
        p.NOMEDELIVERY,
        MIN(p.DATAABERTURA) AS PRIMEIRO_PEDIDO
    FROM
        VWPEDIDOSDELIVERY p
    WHERE
        p.FONEPRINCIPAL IS NOT NULL AND
        p.FONEPRINCIPAL != '' AND
        EXTRACT(WEEKDAY FROM p.DATAABERTURA) IN (5, 6, 0) AND
        p.DATAABERTURA >= CURRENT_DATE - 10
    GROUP BY
        p.FONEPRINCIPAL, p.NOMEDELIVERY
    ORDER BY PRIMEIRO_PEDIDO
    """

    resultados = executar_consulta(sql)

    for telefone_raw, nome_raw, data_pedido in resultados:
        numero = validar_numero(telefone_raw)
        if not numero:
            continue

        if numero in registros_enviados:
            continue

        if fimdesemana_passado(data_pedido):
            nome = formatar_nome(nome_raw)
            mensagem1 = f"""
Oi {nome}! Aqui é o Mr. Teddy 🐻 agradecendo pelo seu pedido!

Fica de olho… na próxima sexta tem mimo especial só pra quem volta!
"""
            adicionar_na_fila({
                "numero": numero,
                "nome": nome,
                "mensagem": urllib.parse.quote(mensagem1.strip()),
                "log": "Mensagem 1 (agradecimento VIP) adicionada à fila"
            })
            novos_registros[numero] = {
                "nome": nome,
                "data": data_pedido.isoformat()
            }

    # Envio da mensagem 2 na sexta-feira às 17:50
    if hoje_sexta_promocao():
        for numero, info in list(registros_enviados.items()):
            try:
                data_registro = datetime.fromisoformat(info['data'])
                if fimdesemana_passado(data_registro):
                    mensagem2 = f"""
Hoje é sexta… e conforme prometido, o Teddy te escolheu pra ganhar um mimo no pedido deste final de semana😍

Pediu dois finais de semana seguidos, leva um Guaraná de 1,5l no pedido de qualquer pizza!!

Responda aqui e já garanta sua pizza e seu refri do final de semana🐻🍕
"""
                    adicionar_na_fila({
                        "numero": numero,
                        "nome": info['nome'],
                        "mensagem": urllib.parse.quote(mensagem2.strip()),
                        "caminho_video": os.path.abspath(IMAGEM_MIMO),
                        "log": "Mensagem 2 (sexta VIP) adicionada à fila"
                    })
                    marcar_como_enviado(numero)
                    novos_registros.pop(numero)
            except Exception as e:
                print(f"❌ Erro ao processar número {numero}: {e}")

    salvar_json(novos_registros)
