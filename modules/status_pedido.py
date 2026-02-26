# modules/status_pedido.py
from datetime import datetime, timedelta
from core.database import executar_consulta
from utils.formatters import formatar_nome, validar_numero
from utils.status_tracker import carregar_status_anteriores, salvar_status_atuais, status_mudou
from utils.message_queue import adicionar_na_fila, registrar_log
import urllib.parse
import os

ultima_execucao = datetime.min
intervalo_execucao = timedelta(seconds=25)

MENSAGENS = {
    'P': "Olá {nome}! O Teddy já esta preparando a sua pizza! Em breve vai sair do forno! 😋",
    'A': "Olá {nome}! Sua pizza está pronta para ser retirada! 🐻",
    'S': "Olá {nome}! Sua pizza acabou de sair para entrega! Fique de olho! 🛵",
    'F': "Olá {nome}!! 🍕\n\nGostou da pizza? Nos ajude deixando uma avaliação no Google, chique que só!\n\n**Clique aqui e deixe o seu comentário **\n\nhttps://g.page/r/CeJ6t3q6aA2UEAE/review\n\nValeu pela força\n\nUrsosamente,\nTeddy 🐻"

}

VIDEOS = {
    'P': "videos/status_pedidos/em_preparacao.mp4",
    'A': "videos/status_pedidos/pronto_retirada.mp4",
    'S': "videos/status_pedidos/saiu_entrega.mp4",
    'F': "videos/status_pedidos/satisfacao.png"
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
        SELECT p.CODIGO, p.DATAABERTURA, p.NOMEDELIVERY, p.FONEPRINCIPAL, p.STATUS, p.ENDERECO, p.ENDERECONUMERO
        FROM VWPEDIDOSDELIVERY p
        WHERE CAST(DATAABERTURA AS DATE) = CURRENT_DATE;
    """
    resultados = executar_consulta(sql)

    status_anteriores = carregar_status_anteriores()
    status_atuais = {}

    for codigo, _, nome_raw, telefone_raw, status, endereco, numero_endereco in resultados:
        try:
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
        except Exception as e:
            print(f"❌ Erro ao preparar envio do pedido {codigo}: {e}")
    salvar_status_atuais(status_atuais)
