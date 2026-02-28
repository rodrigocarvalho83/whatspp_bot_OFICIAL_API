# modules/satisfacao.py
from datetime import datetime
from core.database import executar_consulta
from utils.formatters import formatar_nome, validar_numero
from utils.sent_satisfacao import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os

TEMPLATE_SATISFACAO = os.getenv("WHATSAPP_TEMPLATE_SATISFACAO", "pesquisa_satisfacao")
TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", TEMPLATE_SATISFACAO)

ultima_execucao = datetime.min

# Executa todos os dias às 10:22
intervalo_execucao = 60  # em minutos

def should_run():
    agora = datetime.now()
    return agora.hour == 10 and agora.minute == 22

# Para testes: descomente para ignorar horário
# def should_run():
#    return True

def run(driver):
    sql = """
        SELECT 
            c.NOME, 
            c.FONEPRINCIPAL,
            count(p.CODIGO) AS quantidade_pedidos,  
            MAX(p.DATAABERTURA) AS ultimo_pedido,
            EXTRACT(DAY FROM MAX(p.DATAABERTURA)) AS DIA,
            EXTRACT(MONTH FROM MAX(p.DATAABERTURA)) AS MES,
            EXTRACT(YEAR FROM MAX(p.DATAABERTURA)) AS ANO,
            SUM(p.VALORTOTALITENS) AS valor_gasto
        FROM 
            pedidos p 
            INNER JOIN contatos c ON p.codigocontatocliente = c.codigo
        WHERE 
            FONEPRINCIPAL IS NOT NULL 
            AND FONEPRINCIPAL != '00000-0000' 
            AND FONEPRINCIPAL != '' 
        GROUP BY 
            c.NOME, c.FONEPRINCIPAL 
        HAVING 
            MAX(p.DATAABERTURA) > CURRENT_DATE - 1
        ORDER BY 
            ultimo_pedido DESC;
    """
    contatos = executar_consulta(sql)

    for nome_raw, telefone_raw, *_ in contatos:
        if not nome_raw or not telefone_raw:
            continue

        numero = validar_numero(telefone_raw)
        if not numero or ja_enviado(numero):
            continue

        nome = formatar_nome(nome_raw)
        mensagem_texto = f"Olá {nome}!! Como estava sua pizza de ontem? 🍕\n\nGostou da pizza? Então faça um urso feliz e diz pra gente o que achou dela.\nÉ rapidinho, juro pelas minhas garras. É uma pesquisa do Google, chique que só!\n\n**Clique aqui e deixe seu elogio (ou reclamação, mas com jeitinho, você não gostaria de irritar um urso né!?**\n\nhttps://g.page/r/CeJ6t3q6aA2UEAE/review\n\nValeu pela força, e lembre-se: traição é pedir pizza em outro lugar!\n\nUrsosamente,\nTeddy 🐻"
        mensagem = urllib.parse.quote(mensagem_texto)

        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": None,
            "template_name": TEMPLATE_SATISFACAO,
            "template_params": {"nome": nome},
            "template_lang": "pt_BR",
            "fallback_template_name": TEMPLATE_REENGAJAMENTO_MARKETING,
            "fallback_template_params": {"nome": nome},
            "log": "Pesquisa de satisfação enviada"
        })
        marcar_como_enviado(numero)
        registrar_log(numero, nome, "Pesquisa de satisfação enviada")
