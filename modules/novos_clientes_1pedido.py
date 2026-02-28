# Envia mensagens para pessoas que fizeram só 1 pedido nos ultimos 120 dias sem cupom
from datetime import datetime, timedelta
import random
from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os

TEMPLATE_NOVO_CLIENTE_PROMO_48 = os.getenv("WHATSAPP_TEMPLATE_NOVO_CLIENTE_PROMO_48", "novo_cliente_promocao_48")
TEMPLATE_NOVO_CLIENTE_SEGUNDO_PEDIDO = os.getenv("WHATSAPP_TEMPLATE_NOVO_CLIENTE_SEGUNDO_PEDIDO", "novo_cliente_segundo_pedido")
TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", TEMPLATE_NOVO_CLIENTE_PROMO_48)


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
    return agora.strftime('%H:%M') == '17:48' and agora.weekday() != 0  # Não roda na segunda-feira

def dentro_do_horario():
    hora = datetime.now().time()
    return hora.strftime('%H:%M') >= '11:00' and hora.strftime('%H:%M') <= '23:30'

def run(driver):
    sql = """
        SELECT FIRST 21* FROM (
            select 
                c.NOME, 
                c.FONEPRINCIPAL,
                count(p.CODIGO) AS quantidade_pedidos,  
                MAX(p.DATAABERTURA) AS ultimo_pedido,
                EXTRACT(DAY FROM MAX(p.DATAABERTURA)) AS DIA,
                EXTRACT(MONTH FROM MAX(p.DATAABERTURA)) AS MES,
                EXTRACT(YEAR FROM MAX(p.DATAABERTURA)) AS ANO,
                SUM(p.VALORTOTALITENS) AS valor_gasto
            from 
                pedidos p 
                INNER JOIN contatos c ON p.codigocontatocliente = c.codigo
                WHERE (FONEPRINCIPAL IS NOT NULL AND FONEPRINCIPAL != '00000-0000' AND FONEPRINCIPAL != '') AND p.CODIGOCUPOM IS NULL 
                GROUP BY c.NOME, c.FONEPRINCIPAL 
                ORDER BY ultimo_pedido ASC)
        WHERE quantidade_pedidos = 1 
            AND valor_gasto > 0 
            AND valor_gasto IS NOT NULL
            AND ultimo_pedido BETWEEN current_date -127 AND current_date -7
            AND DIA = EXTRACT(DAY FROM CURRENT_DATE)
        ORDER BY valor_gasto desc;
    """
    mensagens_promocao_48 = [
        "{nome}, aqui é o Teddy.\nVocê achou que podia comer uma vez, sumir, e que eu ia esquecer?\n\nAchou errado! 😠\n\nTá rolando mais de *20 SABORES por R$48*, mas só de *TERÇA a QUINTA*...\n\nAproveita antes que minha paciência acabe (e olha que já tá no fim).\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome}, aqui é o Teddy novamente.\nDetectei um padrão: faz o primeiro pedido e... PUF, desaparece!\n\nMas agora tem pizza boa e barata de *TERÇA A QUINTA*.\n*Mais de 20 sabores por R$48*.\n\nVai me ignorar de novo? Vai mesmo? 👀\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome} você experimentou e achou que tava tudo bem sumir?\n\nErrado.\n\nAqui é o Teddy.\nE eu quero te ver aqui *entre TERÇA e QUINTA*, aproveitando *20 SABORES de pizza por R$48*.\n\nSe não vier, eu coloco seu nome na lista negra dos cilentes fantasmas. 👻🍕\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*"
    ]

    mensagens_cupom_20 = [
        "{nome}, aqui é o Teddy! 🐻\nVocê fez seu primeiro pedido e depois desapareceu!\nAcha mesmo que eu não ia sentir falta?\nToma aqui *20% de desconto* no segundo pedido com o cupom *SEGUNDOPEDIDO*. Só vale pro fim de semana!\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",
        "{nome}, Teddy falando.\nVocê me traiu depois do primeiro pedido? Eu confiei em você!\nMas sou um urso de coração mole...\n\n Toma *20% de desconto* no segundo pedido. Use *SEGUNDOPEDIDO* só de sexta a domingo.\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",
        "Ei {nome}! É o Teddy.\nTá achando que amizade é de uma fatia só?\n\nVolta aqui com *20% de desconto* usando o cupom *SEGUNDOPEDIDO*. Só vale entre sexta e domingo!\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*"
    ]

    resultados = executar_consulta(sql)
    dia_semana = datetime.now().weekday()  # 0 = segunda, 6 = domingo

    for nome_raw, telefone_raw, *_ in resultados:
        if not nome_raw or not telefone_raw:
            continue

        numero = validar_numero(telefone_raw)
        if not numero:# or not dentro_do_horario():
            continue

        nome = formatar_nome(nome_raw)
        chave = f"NOVOCLIENTE-{numero}"

        #if ja_enviado(chave):
        #    continue

        if dia_semana in [1, 2, 3]:  # terça, quarta, quinta
            mensagem_texto = random.choice(mensagens_promocao_48).format(nome=nome)
            caminho_video = os.path.abspath("videos/promo/48reais.png")
            template_name = TEMPLATE_NOVO_CLIENTE_PROMO_48
            log_mensagem = "Mensagem para cliente novo - promoção R$48 enviada"
        elif dia_semana in [4, 5, 6]:  # sexta, sábado, domingo
            mensagem_texto = random.choice(mensagens_cupom_20).format(nome=nome)
            caminho_video = os.path.abspath("videos/clube_fimdesemana/teddy_ultimato.mp4")
            template_name = TEMPLATE_NOVO_CLIENTE_SEGUNDO_PEDIDO
            log_mensagem = "Cliente novo 1 pedido 120 dias sem cupom- SEGUNDOPEDIDO enviada"
        else:
            continue

        mensagem = urllib.parse.quote(mensagem_texto)

        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": caminho_video,
            "template_name": template_name,
            "template_params": {"nome": nome},
            "template_lang": "pt_BR",
            "fallback_template_name": TEMPLATE_REENGAJAMENTO_MARKETING,
            "fallback_template_params": {"nome": nome},
            "log": log_mensagem
        })
       
        marcar_como_enviado(chave)
        registrar_log(numero, nome, log_mensagem)