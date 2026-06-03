# Envia mensagens para pessoas que fizeram 2 ou mais pedidos e já não pedem a mais de 40 dias
from datetime import datetime, timedelta
import random
from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os

TEMPLATES_RECUPERA_PROMO_48 = [
    os.getenv("WHATSAPP_TEMPLATE_RECUPERA_PROMO_1", "template_recupera_cliente_promo_1"),
    os.getenv("WHATSAPP_TEMPLATE_RECUPERA_PROMO_2", "template_recupera_cliente_promo_2"),
    os.getenv("WHATSAPP_TEMPLATE_RECUPERA_PROMO_3", "template_recupera_cliente_promo_3"),
    os.getenv("WHATSAPP_TEMPLATE_RECUPERA_PROMO_4", "template_recupera_cliente_promo_4"),
]

TEMPLATES_RECUPERA_CUPOM_20 = [
    os.getenv("WHATSAPP_TEMPLATE_RECUPERA_CUPOM_1", "template_recupera_cliente_cupom_1"),
    os.getenv("WHATSAPP_TEMPLATE_RECUPERA_CUPOM_2", "template_recupera_cliente_cupom_2"),
    os.getenv("WHATSAPP_TEMPLATE_RECUPERA_CUPOM_3", "template_recupera_cliente_cupom_3"),
    os.getenv("WHATSAPP_TEMPLATE_RECUPERA_CUPOM_4", "template_recupera_cliente_cupom_4"),
]

TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", TEMPLATES_RECUPERA_PROMO_48[0])

TEMPLATE_HEADER_VIDEO_PROMO_48 = os.getenv(
    "WHATSAPP_TEMPLATE_RECUPERA_PROMO_VIDEO_URL",
    "https://mrteddypizza.com.br/midia/promo/teddy_bravo_53reais.mp4",
)
TEMPLATE_HEADER_VIDEO_CUPOM_20 = os.getenv(
    "WHATSAPP_TEMPLATE_RECUPERA_CUPOM_VIDEO_URL",
    "https://mrteddypizza.com.br/midia/clube_fimdesemana/teddy_ultimato.mp4",
)


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
    return agora.strftime('%H:%M') == '17:49' and agora.weekday() != 0  # Não roda na segunda-feira

def dentro_do_horario():
    hora = datetime.now().time()
    return hora.strftime('%H:%M') >= '11:00' and hora.strftime('%H:%M') <= '23:30'

def run(driver):
    sql = """
		SELECT * FROM
		(select
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
            WHERE (FONEPRINCIPAL IS NOT NULL AND  FONEPRINCIPAL != '00000-0000' AND FONEPRINCIPAL != '') AND c.nome NOT LIKE '%*Excluído * %'
            GROUP BY c.NOME, c.FONEPRINCIPAL 
            ORDER BY valor_gasto DESC)
		WHERE dia = EXTRACT(DAY FROM CURRENT_DATE) AND ULTIMO_PEDIDO < CURRENT_DATE - 40 and QUANTIDADE_PEDIDOS >= 2
		ORDER BY valor_gasto desc, ultimo_pedido desc;
    """
    mensagens_promocao_48 = [
        "{nome}, aqui é o Teddy.\nSumido hein? Tá achando que *pizza de R$53,99* com mais de *15 sabores* cai do céu?\n\nVolta logo antes que eu vá te buscar! 👊🍕\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome}, eu tava tranquilo… até lembrar que você sumiu!\nMais de *15 sabores por R$53,99* e você aí de dieta?\n\nNão me provoque.\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "Tô cansado de ser bonzinho, {nome}.\n*Promoção R$53,99, terça a quinta.*\n\nSe ignorar isso, vamos ter um problema. 😤\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome}, mais de 40 dias sem dar as caras?\nVocê não vai resistir: *15 pizzas por R$53,99*.\n\nVolta antes que eu vá aí te buscar. 🧸🚫\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "Sumido igual fantasma, né {nome}? 👻\nMas vou te assombrar com essa promo: *15 sabores por R$53,99*.\n\nDe terça a quinta. Vem antes que eu vá aí te buscar.\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome}, lembra da gente?\nVocê, eu, e aquela pizza delicinha…\n\nVolta logo, R$53,99 tá barato demais pra você perder!\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*"
    ]

    mensagens_cupom_20 = [
        "{nome}, OI SUMIDO!\nAproveite *20% de desconto* no final de semana com o *cupom OISUMIDO*.\n\nVolta logo ou eu vou te bloquear emocionalmente! 😢🍕\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome}, aqui é o Teddy.\nVocê sumiu por 2 meses… mas eu perdoo.\nSe usar o *cupom OISUMIDO* no fim de semana. 😏\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome}, você tem o FIM DE SEMANA pra provar que ainda me ama.\nUse o *cupom OISUMIDO* e ganhe *20% de desconto*.\nOu eu sigo em frente com outro cliente. 💔\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "Teddy aqui. 40 dias sem sinal de vida, {nome}?\nAí vai um presente de reconciliação: *20% OFF* no fim de semana com o *cupom OISUMIDO*.\n\nSe não aceitar, vou chorar no forno.\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "{nome}, parei de assistir séries só pra vir aqui te dar isso:\n\n*20% de desconto* no pedido durante o final de semana.\nCupom: OISUMIDO\nTeddy te espera!\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*",

        "Eu pensei em te bloquear, {nome}.\nMas em vez disso... decidi te dar mais uma chance.\n*Cupom OISUMIDO*, *20% OFF* durante o final de semana.\nMe surpreenda.\n\nhttps://vilamaria.mrteddypizza.com.br\n\n*Abertura da pizzaria: 18:00hrs*"
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
        chave = f"RECUPERA-CLIENTE-40d-{numero}"

        #if ja_enviado(chave):
        #    continue

        if dia_semana in [1, 2, 3]:  # terça, quarta, quinta
            mensagem_texto = random.choice(mensagens_promocao_48).format(nome=nome)
            caminho_video = os.path.abspath("videos/clube_fimdesemana/teddy_ultimato.mp4")
            template_name = random.choice(TEMPLATES_RECUPERA_PROMO_48)
            template_header_media = {"type": "video", "link": TEMPLATE_HEADER_VIDEO_PROMO_48}
            log_mensagem = f"Recupera clientes mais de 90d - promoção R$53,99 enviada (template={template_name})"
        elif dia_semana in [4, 5, 6]:  # sexta, sábado, domingo
            mensagem_texto = random.choice(mensagens_cupom_20).format(nome=nome)
            caminho_video = os.path.abspath("videos/clube_fimdesemana/teddy_ultimato.mp4")
            template_name = random.choice(TEMPLATES_RECUPERA_CUPOM_20)
            template_header_media = {"type": "video", "link": TEMPLATE_HEADER_VIDEO_CUPOM_20}
            log_mensagem = f"Recupera clientes mais de 90d - OISUMIDO enviada (template={template_name})"
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
            "template_header_media": template_header_media,
            "fallback_template_name": TEMPLATE_REENGAJAMENTO_MARKETING,
            "fallback_template_params": {"nome": nome},
            "log": log_mensagem
        })
       
        marcar_como_enviado(chave)
        registrar_log(numero, nome, log_mensagem)
