# Envia cupom de SEGUNDOPEDIDO para pessoas que fizeram o primerio pedido na semana atual, entre ter e qui.
from datetime import datetime, timedelta
from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os

TEMPLATE_SEGUNDO_PEDIDO = os.getenv("WHATSAPP_TEMPLATE_SEGUNDO_PEDIDO", "template_clube_segundopedido")
TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", TEMPLATE_SEGUNDO_PEDIDO)
TEMPLATE_HEADER_IMAGE_URL = os.getenv(
    "WHATSAPP_TEMPLATE_SEGUNDO_PEDIDO_HEADER_IMAGE_URL",
    "https://mrteddypizza.com.br/midia/clube_fimdesemana/teddy_convite.png",
)


# Teste execução a cada minuto
#ultima_execucao = datetime.min
#intervalo_execucao = timedelta(seconds=60)
#def should_run():
#    global ultima_execucao
#    agora = datetime.now()
#    if agora - ultima_execucao >= intervalo_execucao:
#        ultima_execucao = agora
#        return True
#    return False


def should_run():
    agora = datetime.now()
    return agora.weekday() == 4 and agora.strftime('%H:%M') == '18:10'  # Sexta-feira às 18:10

def dentro_do_horario():
    hora = datetime.now().time()
    return hora.strftime('%H:%M') >= '11:00' and hora.strftime('%H:%M') <= '23:30'

def run(driver):
    sql = """
        SELECT 
          c.NOME, 
          c.FONEPRINCIPAL,
          COUNT(p.CODIGO) AS quantidade_pedidos,  
          MAX(p.DATAABERTURA) AS ultimo_pedido,
          EXTRACT(DAY FROM MAX(p.DATAABERTURA)) AS dia_ultimo_pedido,
          EXTRACT(MONTH FROM MAX(p.DATAABERTURA)) AS mes_ultimo_pedido,
          EXTRACT(YEAR FROM MAX(p.DATAABERTURA)) AS ano_ultimo_pedido,
          SUM(p.VALORTOTALITENS) AS valor_gasto
        FROM 
          pedidos p 
          INNER JOIN contatos c ON p.codigocontatocliente = c.codigo
        WHERE 
          c.FONEPRINCIPAL IS NOT NULL 
          AND c.FONEPRINCIPAL != '00000-0000' 
          AND c.FONEPRINCIPAL != ''
        GROUP BY 
          c.NOME, c.FONEPRINCIPAL
        HAVING 
          COUNT(p.CODIGO) = 1 and  MAX(p.DATAABERTURA) > CURRENT_DATE - 3
        ORDER BY 
          ultimo_pedido DESC;
    """

    resultados = executar_consulta(sql)
    
    for nome_raw, telefone_raw, *_ in resultados:
        if not nome_raw or not telefone_raw:
            continue

        numero = validar_numero(telefone_raw)
        if not numero or not dentro_do_horario():
            continue

        nome = formatar_nome(nome_raw)
        chave = f"2PEDIDO-{numero}"

        #if ja_enviado(chave):
        #    continue
        
        mensagem_texto = (
            f"Olá {nome}, aqui é o Teddy! 🐻\nFiquei sabendo que você fez seu PRIMEIRO pedido essa semana...gostei de você!😅🍕\n\nAqui vai um “suborno” oficial: *20% DE DESCONTO* no seu SEGUNDO pedido!\nUse o cupom: *SEGUNDOPEDIDO*\n\nAproveita, antes que eu coma tudo sozinho! 😋\nPromoção válida só esse fim de semana!\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*"
        )
        
        mensagem = urllib.parse.quote(mensagem_texto)
        caminho_video = os.path.abspath("videos/clube_fimdesemana/teddy_convite.jpg")
                
        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": caminho_video,
            "template_name": TEMPLATE_SEGUNDO_PEDIDO,
            "template_params": {"nome": nome},
            "template_lang": "pt_BR",
            "template_header_media": {"type": "image", "link": TEMPLATE_HEADER_IMAGE_URL},
            "fallback_template_name": TEMPLATE_REENGAJAMENTO_MARKETING,
            "fallback_template_params": {"nome": nome},
            "log": "Cupom de segundo pedido enviado para cliente novo"
        })
       
        marcar_como_enviado(chave)
        registrar_log(numero, nome, "Envio cupom SEGUNDOPEDIDO enviada")
