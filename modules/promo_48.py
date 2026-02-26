# Envia mensagens, na terça feira, para pessoas que fizeram só 1 pedido, utilizando CUPOM
from datetime import datetime, timedelta
import random
from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os


# Teste execução a cada minuto
# ultima_execucao = datetime.min
# intervalo_execucao = timedelta(seconds=60)
# def should_run():
#     global ultima_execucao
#     agora = datetime.now()
#     if agora - ultima_execucao >= intervalo_execucao:
#         ultima_execucao = agora
#         return True
#     return False


def should_run():
    agora = datetime.now()
    return agora.weekday() == 1 and agora.strftime('%H:%M') == '17:01'  # Terça-feira às 17:42

def dentro_do_horario():
    hora = datetime.now().time()
    return hora.strftime('%H:%M') >= '11:00' and hora.strftime('%H:%M') <= '23:30'

def run(driver):
    sql = """
    SELECT FIRST 20 * FROM        
        (SELECT 
        c.NOME, 
        c.FONEPRINCIPAL,
        COUNT(p.CODIGO) AS quantidade_pedidos,  
        MAX(p.DATAABERTURA) AS ultimo_pedido,
        EXTRACT(DAY FROM MAX(p.DATAABERTURA)) AS dia_ultimo_pedido,
        EXTRACT(MONTH FROM MAX(p.DATAABERTURA)) AS mes_ultimo_pedido,
        EXTRACT(YEAR FROM MAX(p.DATAABERTURA)) AS ano_ultimo_pedido,
        LIST(DISTINCT p.CODIGOCUPOM, ', ') AS codigos_cupons,
        SUM(p.VALORTOTALITENS) AS valor_gasto
      FROM 
        pedidos p 
        INNER JOIN contatos c ON p.codigocontatocliente = c.codigo
      WHERE 
        c.FONEPRINCIPAL IS NOT NULL 
        AND c.FONEPRINCIPAL != '00000-0000' 
        AND c.FONEPRINCIPAL != ''
        --AND c.FONEPRINCIPAL LIKE '%99233-2393'
      GROUP BY 
        c.NOME, c.FONEPRINCIPAL
      ORDER BY 
        ultimo_pedido DESC)
      WHERE 
        QUANTIDADE_PEDIDOS = 1 AND ( 
        CODIGOS_CUPONS LIKE '%1%' OR
        CODIGOS_CUPONS LIKE '%2%' OR
        CODIGOS_CUPONS LIKE '%3%' OR
        CODIGOS_CUPONS LIKE '%4%')
      ORDER BY VALOR_GASTO DESC;
    """
    mensagens_opcoes = [
        "{nome}, aqui é o Teddy.\nVocê achou que podia comer uma vez, sumir, e que eu ia esquecer?\n\nAchou errado, cuponzeiro! 😠\n\nTá rolando mais de *20 SABORES por R$48*, mas só de *TERÇA a QUINTA*...\n\nAproveita antes que minha paciência acabe (e olha que já tá no fim).\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome}, aqui é o Teddy novamente.\nDetectei um padrão: cuponzeiro faz o primeiro pedido e... PUF, desaparece!\n\nMas agora tem pizza boa e barata de *TERÇA A QUINTA*.\n*Mais de 20 sabores por R$48*.\n\nVai me ignorar de novo? Vai mesmo? 👀\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome} você usou um cupom e achou que tava tudo bem sumir?\n\nErrado.\n\nAqui é o Teddy.\nE eu quero te ver aqui *entre TERÇA e QUINTA*, aproveitando *20 SABORES de pizza por R$48*.\n\nSe não vier, eu coloco seu nome na lista negra dos cuponzeiros fantasmas. 👻🍕\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*"
    ]

    resultados = executar_consulta(sql)
    
    for nome_raw, telefone_raw, *_ in resultados:
        if not nome_raw or not telefone_raw:
            continue

        numero = validar_numero(telefone_raw)
        if not numero:# or not dentro_do_horario():
            continue

        nome = formatar_nome(nome_raw)
        chave = f"48REAIS-{numero}"

        #if ja_enviado(chave):
        #    continue
        
        #mensagem_texto = (
        #    f"Olá {nome}, aqui é o Teddy! 🐻\nFiquei sabendo que você fez seu PRIMEIRO pedido essa semana...gostei de você!😅🍕\n\nAqui vai um “suborno” oficial: *20% DE DESCONTO* no seu SEGUNDO pedido!\nUse o cupom: *SEGUNDOPEDIDO*\n\nAproveita, antes que eu coma tudo sozinho! 😋\nPromoção válida só esse fim de semana!\n\nhttps://vilamaria.mrteddypizza.com.br"
        #)


        mensagem_texto = random.choice(mensagens_opcoes).format(nome=nome)
        mensagem = urllib.parse.quote(mensagem_texto)
        caminho_video = os.path.abspath("videos/promo/teddy_bravo.jpeg")
                
        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": caminho_video,
            "log": "Clientes 1 pedido com cupom - PROMO R$48"
        })
       
        marcar_como_enviado(chave)
        registrar_log(numero, nome, "Clientes 1 pedido com cupom - PROMO R$48")
