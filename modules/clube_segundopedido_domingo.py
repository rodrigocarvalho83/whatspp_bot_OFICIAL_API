# Envia cupom de SEGUNDOPEDIDO para pessoas que fizeram o primerio pedido na semana atual, entre ter e qui.
from datetime import datetime, timedelta
from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os

TEMPLATE_SEGUNDO_PEDIDO_LEMBRETE = os.getenv("WHATSAPP_TEMPLATE_SEGUNDO_PEDIDO_LEMBRETE", "clube_segundo_pedido_lembrete")
TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", TEMPLATE_SEGUNDO_PEDIDO_LEMBRETE)


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
    return agora.weekday() == 6 and agora.strftime('%H:%M') == '17:00'  # Sexta-feira às 17:00

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
          COUNT(p.CODIGO) = 1 and  MAX(p.DATAABERTURA) BETWEEN CURRENT_DATE - 5 AND current_date - 2
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
        chave = f"2PEDIDO-LEMBRETE-{numero}"

        #if ja_enviado(chave):
        #    continue
        
        mensagem_texto = (
            f"{nome}, você ignorou o cupom…\nMas será que consegue ignorar 2 metros de fúria, fome e pelúcia batendo palmas na sua janela? 👏🐻\n\nUsa logo o cupom *SEGUNDOPEDIDO*!\n\nSe não, a próxima visita não vai ser pelo WhatsApp… 😠\n\nVálido só para o fim de semana!!\n\n*Abertura da pizzaria: 18:00hrs*"
        )
        
        mensagem = urllib.parse.quote(mensagem_texto)
        caminho_video = os.path.abspath("videos/clube_fimdesemana/teddy_ultimato.mp4")
                
        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": caminho_video,
            "template_name": TEMPLATE_SEGUNDO_PEDIDO_LEMBRETE,
            "template_params": {"nome": nome},
            "template_lang": "pt_BR",
            "fallback_template_name": TEMPLATE_REENGAJAMENTO_MARKETING,
            "fallback_template_params": {"nome": nome},
            "log": "Reenvio no domingo cupom de segundo pedido enviado para cliente novo"
        })
       
        marcar_como_enviado(chave)
        registrar_log(numero, nome, "Reenvio cupom SEGUNDOPEDIDO")
