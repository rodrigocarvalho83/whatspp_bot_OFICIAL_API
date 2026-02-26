# modules/cartao_fidelidade.py
from datetime import datetime, timedelta
from core.database import executar_consulta
from utils.formatters import formatar_nome, validar_numero
from utils.sent_status import marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila
import urllib.parse
import os
import json

#TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", "hello_world")
TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", "cartao_fidelidade_update")
ultima_execucao = datetime.min
intervalo_execucao = timedelta(seconds=60)

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
        print("📄 Arquivo de saldos não encontrado. Inicializando com registros atuais.")
        inicializando_saldos = True
        return {}
    try:
        with open(CAMINHO_SALDOS, encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print("📄 Arquivo de saldos vazio. Inicializando com registros atuais.")
                inicializando_saldos = True
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Erro ao carregar {CAMINHO_SALDOS}: {e}")
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
        #print(f"\n👤 Cliente: {codigo} | Nome: {nome_raw} | Telefone: {telefone_raw} | Saldo Atual: {saldoatual}")

        if not nome_raw or not telefone_raw:
            #print("⏭️ Nome ou telefone vazio, ignorando...")
            continue

        numero = validar_numero(telefone_raw)
        if not numero:
            #print(f"⏭️ Telefone inválido após validação: {telefone_raw}")
            continue

        #if not dentro_do_horario():
        #    print("⏰ Fora do horário de envio.")
        #    continue

        saldo_antigo = saldos_anteriores.get(str(codigo), {}).get("pontos")
        #print(f"📌 Saldo antigo: {saldo_antigo} | Inicializando: {inicializando_saldos}")

        novos_saldos[str(codigo)] = {
            "pontos": int(saldoatual),
            "telefone": numero
        }

        if not inicializando_saldos and saldo_antigo == saldoatual:
            #print("🔁 Saldo não mudou. Ignorando envio.")
            continue

        print("✅ Enviando mensagem de fidelidade...\n👤 Cliente: {codigo} | Nome: {nome_raw} | Telefone: {telefone_raw} | Saldo Atual: {saldoatual}\n📌 Saldo antigo: {saldo_antigo} | Inicializando: {inicializando_saldos}\n\n")
        
        nome = formatar_nome(nome_raw)

        if saldoatual == 0:
            mensagem = f"""
*CARTÃO FIDELIDADE MR. TEDDY*
Olá, {nome}!
Seja bem vindo!

Aqui na Mr. Teddy cada pizza comprada gera 1 ponto no seu cartão fidelidade.
Ao acumular 12 pontos, você pode trocá-los por uma pizza *Tradicional GRÁTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoção.
Equipe Mr. Teddy
"""
        elif saldoatual == 10:
            mensagem = f"""
*CARTÃO FIDELIDADE MR. TEDDY*
Olá, {nome}!
Agora falta pouco!!!
Só mais duas pizzas e você poderá trocar seus pontos por uma pizza *Tradicional GRÁTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoção.
Equipe Mr. Teddy
"""
        elif saldoatual == 11:
            mensagem = f"""
*CARTÃO FIDELIDADE MR. TEDDY*
Olá, {nome}!
Você está quase lá!!!
Só mais uma pizza e você poderá trocar seus pontos por uma pizza *Tradicional GRÁTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoção.
Equipe Mr. Teddy
"""
        elif saldoatual >= 12:
            mensagem = f"""
*CARTÃO FIDELIDADE MR. TEDDY*
Olá, {nome}!

*PARABÉNS!!!*
Você acumulou {saldoatual} pontos e pode trocá-los por uma pizza *Tradicional GRÁTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoção.
Equipe Mr. Teddy
"""
        else:
            mensagem = f"""
*CARTÃO FIDELIDADE MR. TEDDY*
Olá, {nome}!

Você acaba de acumular mais ponto(s) no seu cartão fidelidade.
Ao acumular 12 pontos, você pode trocá-los por uma pizza *Tradicional GRÁTIS*!!

*SALDO DE PONTOS:* {saldoatual}
Aproveite a promoção.
Equipe Mr. Teddy
"""

        imagem = IMAGENS.get(saldoatual, IMAGENS["default"])
        mensagem_url = urllib.parse.quote(mensagem.strip())
        caminho_imagem = os.path.abspath(imagem)

        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem_url,
            "caminho_video": caminho_imagem,
            "force_text_with_media": True,
            "fallback_template_name": TEMPLATE_REENGAJAMENTO_MARKETING,
            "fallback_template_params": [nome, str(saldoatual)],
            "log": f"Cartão fidelidade ({saldoatual} pontos) adicionado à fila"
        })

        marcar_como_enviado(numero, saldoatual)
        registrar_log(numero, nome, "Cartão Fidelidade")

    salvar_saldos_anteriores(novos_saldos)
