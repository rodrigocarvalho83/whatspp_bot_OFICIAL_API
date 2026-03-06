# modules/cartao_fidelidade.py
from datetime import datetime, timedelta
from core.database import executar_consulta
from utils.formatters import formatar_nome, validar_numero
from utils.sent_status import marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os
import json

TEMPLATE_FIDELIDADE = os.getenv("WHATSAPP_TEMPLATE_FIDELIDADE", "template_cartao_fidelidade")
TEMPLATE_FIDELIDADE_12_PONTOS = os.getenv("WHATSAPP_TEMPLATE_FIDELIDADE_12_PONTOS", "template_cartao_fidelidade_12pontos")
TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", TEMPLATE_FIDELIDADE)

ultima_execucao = datetime.min
intervalo_execucao = timedelta(seconds=60)

# IMAGENS LOCAIS USADAS NO ENVIO DE MIDIA (arquivo do projeto):
# - Troque os caminhos abaixo quando mudar os arquivos da pasta `videos/cartao/`.
# - A chave representa a pontuacao atual do cliente.
# - "default" e usada quando saldoatual nao existir no dicionario (ex.: > 12).
IMAGENS = {
    0: "videos/cartao/0pontos.png",
    1: "videos/cartao/1pontos.png",
    2: "videos/cartao/2pontos.png",
    3: "videos/cartao/3pontos.png",
    4: "videos/cartao/4pontos.png",
    5: "videos/cartao/5pontos.png",
    6: "videos/cartao/6pontos.png",
    7: "videos/cartao/7pontos.png",
    8: "videos/cartao/8pontos.png",
    9: "videos/cartao/9pontos.png",
    10: "videos/cartao/10pontos.png",
    11: "videos/cartao/11pontos.png",
    12: "videos/cartao/12pontos.png",
    "default": "videos/cartao/12pontos.png"
}
# URL BASE DAS IMAGENS DO HEADER PARA A WHATSAPP CLOUD API:
# - Altere via variavel de ambiente `WHATSAPP_CARTAO_FIDELIDADE_MEDIA_BASE_URL`
#   ou troque o valor padrao abaixo.
# - A API recebera links no formato: {BASE}/{N}pontos.png
MEDIA_BASE_URL_CARTAO = os.getenv(
    "WHATSAPP_CARTAO_FIDELIDADE_MEDIA_BASE_URL",
    "https://mrteddypizza.com.br/midia/cartao",
).rstrip("/")

# URLS POR PONTUACAO ENVIADAS PARA O HEADER DO TEMPLATE:
# - Se a sua estrutura de links nao seguir o padrao da BASE, altere item a item aqui.
# - "default" e usada para pontuacoes fora das chaves (ex.: > 12).
MEDIA_URLS = {
    0: f"{MEDIA_BASE_URL_CARTAO}/0pontos.png",
    1: f"{MEDIA_BASE_URL_CARTAO}/1pontos.png",
    2: f"{MEDIA_BASE_URL_CARTAO}/2pontos.png",
    3: f"{MEDIA_BASE_URL_CARTAO}/3pontos.png",
    4: f"{MEDIA_BASE_URL_CARTAO}/4pontos.png",
    5: f"{MEDIA_BASE_URL_CARTAO}/5pontos.png",
    6: f"{MEDIA_BASE_URL_CARTAO}/6pontos.png",
    7: f"{MEDIA_BASE_URL_CARTAO}/7pontos.png",
    8: f"{MEDIA_BASE_URL_CARTAO}/8pontos.png",
    9: f"{MEDIA_BASE_URL_CARTAO}/9pontos.png",
    10: f"{MEDIA_BASE_URL_CARTAO}/10pontos.png",
    11: f"{MEDIA_BASE_URL_CARTAO}/11pontos.png",
    12: f"{MEDIA_BASE_URL_CARTAO}/12pontos.png",
    "default": f"{MEDIA_BASE_URL_CARTAO}/12pontos.png",
}

CAMINHO_SALDOS = "log/saldos_fidelidade.json"

inicializando_saldos = False

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

def carregar_saldos_anteriores():
    global inicializando_saldos
    if not os.path.exists(CAMINHO_SALDOS):
        print("ðŸ“„ Arquivo de saldos nÃ£o encontrado. Inicializando com registros atuais.")
        inicializando_saldos = True
        return {}
    try:
        with open(CAMINHO_SALDOS, encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print("ðŸ“„ Arquivo de saldos vazio. Inicializando com registros atuais.")
                inicializando_saldos = True
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        print(f"âŒ Erro ao carregar {CAMINHO_SALDOS}: {e}")
        inicializando_saldos = True
        return {}

def salvar_saldos_anteriores(saldos):
                                                                 
    with open(CAMINHO_SALDOS, 'w', encoding='utf-8') as f:
        json.dump(saldos, f, ensure_ascii=False, indent=2)


def run(driver):
    saldos_anteriores = carregar_saldos_anteriores()

    sql = """
      SELECT 
      c.CODIGO,
      c.NOME, 
      c.FONEPRINCIPAL,
      cc.SALDOATUAL
    FROM 
      CAMPANHACONTATO cc 
      INNER JOIN contatos c ON cc.CODIGOCONTATO = c.codigo
      INNER JOIN CAMPANHA ca ON cc.CODIGOCAMPANHA = ca.CODIGO 
    WHERE 
      cc.DATADELETE IS NULL and c.DATADELETE IS NULL and (c.FONEPRINCIPAL IS NOT NULL 
      and c.FONEPRINCIPAL != '00000-0000' and c.FONEPRINCIPAL != '(11)00000-0000' and c.FONEPRINCIPAL != '(00)00000-0000' and c.FONEPRINCIPAL != '(00) 0000-0000' 
      AND c.FONEPRINCIPAL != '' and CHAR_LENGTH(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(c.FONEPRINCIPAL, '(', ''), ')', ''), '-', ''), ' ', ''), '.', ''))) >= 9)
      ORDER BY cc.SALDOATUAL desc;
    """

    resultados = executar_consulta(sql)
    novos_saldos = {}

    for codigo, nome_raw, telefone_raw, saldoatual in resultados:
        #print(f"\nðŸ‘¤ Cliente: {codigo} | Nome: {nome_raw} | Telefone: {telefone_raw} | Saldo Atual: {saldoatual}")

        if not nome_raw or not telefone_raw:
            #print("â­ï¸ Nome ou telefone vazio, ignorando...")
            continue

        numero = validar_numero(telefone_raw)
        if not numero:
            #print(f"â­ï¸ Telefone invÃ¡lido apÃ³s validaÃ§Ã£o: {telefone_raw}")
            continue

        #if not dentro_do_horario():
        #    print("â° Fora do horÃ¡rio de envio.")
        #    continue

        saldo_antigo = saldos_anteriores.get(str(codigo), {}).get("pontos")
        #print(f"ðŸ“Œ Saldo antigo: {saldo_antigo} | Inicializando: {inicializando_saldos}")

        novos_saldos[str(codigo)] = {
            "pontos": int(saldoatual),
            "telefone": numero
        }

        if not inicializando_saldos and saldo_antigo == saldoatual:
            #print("ðŸ” Saldo nÃ£o mudou. Ignorando envio.")
            continue

        print("âœ… Enviando mensagem de fidelidade...\nðŸ‘¤ Cliente: {codigo} | Nome: {nome_raw} | Telefone: {telefone_raw} | Saldo Atual: {saldoatual}\nðŸ“Œ Saldo antigo: {saldo_antigo} | Inicializando: {inicializando_saldos}\n\n")
        
        nome = formatar_nome(nome_raw)

        if saldoatual == 0:
            mensagem = f"""
*CARTÃƒO FIDELIDADE MR. TEDDY*
OlÃ¡, {nome}!
Seja bem vindo!

Aqui na Mr. Teddy cada pizza comprada gera 1 ponto no seu cartÃ£o fidelidade.
Ao acumular 12 pontos, vocÃª pode trocÃ¡-los por uma pizza *Tradicional GRÃTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoÃ§Ã£o.
Equipe Mr. Teddy
"""
        elif saldoatual == 10:
            mensagem = f"""
*CARTÃƒO FIDELIDADE MR. TEDDY*
OlÃ¡, {nome}!
Agora falta pouco!!!
SÃ³ mais duas pizzas e vocÃª poderÃ¡ trocar seus pontos por uma pizza *Tradicional GRÃTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoÃ§Ã£o.
Equipe Mr. Teddy
"""
        elif saldoatual == 11:
            mensagem = f"""
*CARTÃƒO FIDELIDADE MR. TEDDY*
OlÃ¡, {nome}!
VocÃª estÃ¡ quase lÃ¡!!!
SÃ³ mais uma pizza e vocÃª poderÃ¡ trocar seus pontos por uma pizza *Tradicional GRÃTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoÃ§Ã£o.
Equipe Mr. Teddy
"""
        elif saldoatual >= 12:
            mensagem = f"""
*CARTÃƒO FIDELIDADE MR. TEDDY*
OlÃ¡, {nome}!

*PARABÃ‰NS!!!*
VocÃª acumulou {saldoatual} pontos e pode trocÃ¡-los por uma pizza *Tradicional GRÃTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoÃ§Ã£o.
Equipe Mr. Teddy
"""
        else:
            mensagem = f"""
*CARTÃƒO FIDELIDADE MR. TEDDY*
OlÃ¡, {nome}!

VocÃª acaba de acumular mais ponto(s) no seu cartÃ£o fidelidade.
Ao acumular 12 pontos, vocÃª pode trocÃ¡-los por uma pizza *Tradicional GRÃTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoÃ§Ã£o.
Equipe Mr. Teddy
"""
        saldo_int = int(saldoatual)
        # Aqui define qual imagem local sera enviada (upload de midia).
        imagem = IMAGENS.get(saldo_int, IMAGENS["default"])
        # Aqui define qual URL de imagem sera enviada no header do template.
        media_url = MEDIA_URLS.get(saldo_int, MEDIA_URLS["default"])
        mensagem_url = urllib.parse.quote(mensagem.strip())
        caminho_imagem = os.path.abspath(imagem)

        template_escolhido = TEMPLATE_FIDELIDADE if saldo_int < 12 else TEMPLATE_FIDELIDADE_12_PONTOS
        fallback_template = TEMPLATE_REENGAJAMENTO_MARKETING if saldo_int < 12 else TEMPLATE_FIDELIDADE_12_PONTOS
        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem_url,
            "caminho_video": caminho_imagem,
            "force_text_with_media": True,
            "template_name": template_escolhido,
            "template_params": {"nome": nome, "saldoatual": str(saldo_int)},
            "template_lang": "pt_BR",
            "template_header_media": {"type": "image", "link": media_url},
            "fallback_template_name": fallback_template,
            "fallback_template_params": {"nome": nome, "saldoatual": str(saldo_int)},
            "log": f"CartÃ£o fidelidade ({saldoatual} pontos) adicionado Ã  fila"
        })

        marcar_como_enviado(numero, saldoatual)
        registrar_log(numero, nome, "CartÃ£o Fidelidade")

    salvar_saldos_anteriores(novos_saldos)


