# modules/status_pedido.py
from datetime import datetime, timedelta
from core.database import executar_consulta
from utils.formatters import formatar_nome, validar_numero
from utils.status_tracker import carregar_status_anteriores, salvar_status_atuais, status_mudou
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os

ultima_execucao = datetime.min
intervalo_execucao = timedelta(seconds=25)

MENSAGENS = {
    'P': "Olá {nome}! Sua pizza está sendo preparada! Em breve vai sair do forno! 😋",
    'S': "Olá {nome}! Sua pizza acabou de sair para entrega! Fique de olho! 🛵",
    'F': "Olá {nome}! Esperamos que tenha aproveitado sua pizza! Até a próxima! 🍕"
}

VIDEOS = {
    'P': "videos/status_pedidos/em_preparacao.mp4",
    'S': "videos/status_pedidos/saiu_entrega.mp4",
    'F': "videos/status_pedidos/finalizado.mp4"
}

def should_run():
    global ultima_execucao
    agora = datetime.now()
    if agora - ultima_execucao >= intervalo_execucao:
        ultima_execucao = agora
        return True
    return False

def dentro_do_horario():
    agora = datetime.now().time()
    return '11:00' <= agora.strftime('%H:%M') <= '23:30'

def run(driver):
    sql = """
        SELECT CODIGO, NOMEDELIVERY, FONEPRINCIPAL, STATUS, ENDERECO, ENDERECONUMERO
        FROM VWPEDIDOSDELIVERY
        WHERE DATAABERTURA > CURRENT_DATE -1
    """
    resultados = executar_consulta(sql)

    status_anteriores = carregar_status_anteriores()
    status_atuais = {}

    for codigo, nome_raw, telefone_raw, status, endereco, numero_endereco in resultados:
        if not nome_raw or not telefone_raw:
            continue

        numero = validar_numero(telefone_raw)
        if not numero or not dentro_do_horario():
            continue

        if status not in MENSAGENS or status not in VIDEOS:
            print(f"⚠️ Status '{status}' não reconhecido. Ignorando pedido {codigo}.")
            continue

        chave_status = str(codigo)
        status_atuais[chave_status] = status

        if not status_mudou(chave_status, status, status_anteriores):
            continue

        nome = formatar_nome(nome_raw)
        mensagem = urllib.parse.quote(MENSAGENS[status].format(nome=nome))
        caminho_video = os.path.abspath(VIDEOS[status])

        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": caminho_video,
            "log": f"Status '{status}' adicionado à fila de envio"
        })

    salvar_status_atuais(status_atuais)
