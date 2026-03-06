from datetime import datetime
import os
import urllib.parse

from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila

# ==========================================================
# CONFIGURACOES PRINCIPAIS DO DISPARO SOB DEMANDA
# ==========================================================
# 1) DATA/HORA DO DISPARO
# - WHATSAPP_SOB_DEMANDA_DATA: data exata do disparo (formato YYYY-MM-DD)
# - WHATSAPP_SOB_DEMANDA_HORA: hora exata do disparo (formato HH:MM)
# Se a data estiver vazia, o modulo NAO dispara.
DATA_DISPARO = os.getenv("WHATSAPP_SOB_DEMANDA_DATA", "2026-03-05").strip()
HORA_DISPARO = os.getenv("WHATSAPP_SOB_DEMANDA_HORA", "18:52").strip()

# 2) IDENTIFICADOR DA CAMPANHA
# Usado para controle de duplicidade (ja_enviado/marcar_como_enviado).
CAMPANHA_ID = os.getenv("WHATSAPP_SOB_DEMANDA_CAMPANHA_ID", "clientes_inativos").strip()

# 3) NOME DOS TEMPLATES NA META
TEMPLATE_CLIENTES_INATIVOS_IMAGE = os.getenv(
    "WHATSAPP_TEMPLATE_CLIENTES_INATIVOS_IMAGE",
    "template_clientes_inativos_image",
)
TEMPLATE_CLIENTES_INATIVOS_VIDEO = os.getenv(
    "WHATSAPP_TEMPLATE_CLIENTES_INATIVOS_VIDEO",
    "template_clientes_inativos_video",
)
TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv(
    "WHATSAPP_TEMPLATE_MARKETING",
    TEMPLATE_CLIENTES_INATIVOS_IMAGE,
)

# 4) HABILITACAO DE CADA TEMPLATE
# Valores aceitos: 1/0, true/false, sim/nao.
# - Somente IMAGE: IMAGE=1 e VIDEO=0
# - Somente VIDEO: IMAGE=0 e VIDEO=1
# - Ambos alternados: IMAGE=1 e VIDEO=1
HABILITAR_TEMPLATE_IMAGE = os.getenv(
    "WHATSAPP_SOB_DEMANDA_HABILITAR_TEMPLATE_IMAGE",
    "1",
).strip()
HABILITAR_TEMPLATE_VIDEO = os.getenv(
    "WHATSAPP_SOB_DEMANDA_HABILITAR_TEMPLATE_VIDEO",
    "0",
).strip()

# 5) MIDIA DE HEADER DOS TEMPLATES (PLACEHOLDERS)
# Troque para os links reais quando definir as midias finais.
HEADER_IMAGE_URL = os.getenv(
    "WHATSAPP_SOB_DEMANDA_HEADER_IMAGE_URL",
    "https://mrteddypizza.com.br/midia/promo/48reais.png",
)
HEADER_VIDEO_URL = os.getenv(
    "WHATSAPP_SOB_DEMANDA_HEADER_VIDEO_URL",
    "https://example.com/placeholder-clientes-inativos-video.mp4",
)

# 6) MENSAGEM DE APOIO (nao e o template da Meta, apenas texto auxiliar no payload)
MENSAGEM_PADRAO = os.getenv(
    "WHATSAPP_SOB_DEMANDA_MENSAGEM",
    "Oi {nome}, temos uma condicao especial para voce.",
)

# 7) QUERY PADRAO
# Pode ser alterada diretamente aqui, ou sobrescrita por variavel de ambiente
# WHATSAPP_SOB_DEMANDA_SQL.
SQL_SOB_DEMANDA = """
SELECT
    C.NOME,
    C.FONEPRINCIPAL
FROM CONTATOS C
WHERE
    C.DATADELETE IS NULL
    AND C.FONEPRINCIPAL IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM PEDIDOS P
        WHERE P.CODIGOCONTATOCLIENTE = C.CODIGO
          AND P.DATADELETE IS NULL
    )
ORDER BY C.NOME
"""


def _bool_env(valor):
    return str(valor).strip().lower() in {"1", "true", "t", "sim", "s", "yes", "y"}


def should_run():
    if not DATA_DISPARO:
        return False
    agora = datetime.now()
    return agora.strftime("%Y-%m-%d") == DATA_DISPARO and agora.strftime("%H:%M") == HORA_DISPARO


def _obter_templates_ativos():
    templates = []

    if _bool_env(HABILITAR_TEMPLATE_IMAGE):
        templates.append(
            (
                TEMPLATE_CLIENTES_INATIVOS_IMAGE,
                {"type": "image", "link": HEADER_IMAGE_URL},
                "disparo sob demanda (template image)",
            )
        )

    if _bool_env(HABILITAR_TEMPLATE_VIDEO):
        templates.append(
            (
                TEMPLATE_CLIENTES_INATIVOS_VIDEO,
                {"type": "video", "link": HEADER_VIDEO_URL},
                "disparo sob demanda (template video)",
            )
        )

    return templates


def _obter_sql():
    sql_custom = os.getenv("WHATSAPP_SOB_DEMANDA_SQL", "").strip()
    return sql_custom if sql_custom else SQL_SOB_DEMANDA


def run(driver):
    templates_ativos = _obter_templates_ativos()
    if not templates_ativos:
        print("Nenhum template habilitado no modulo disparo_sob_demanda.")
        return

    resultados = executar_consulta(_obter_sql())
    data_execucao = datetime.now().strftime("%Y-%m-%d")
    indice_alternancia = 0

    for nome_raw, telefone_raw in resultados:
        if not nome_raw or not telefone_raw:
            continue

        numero = validar_numero(telefone_raw)
        if not numero:
            continue

        nome = formatar_nome(nome_raw)
        chave = f"SOBDEMANDA-{CAMPANHA_ID}-{data_execucao}-{numero}"
        if ja_enviado(chave):
            continue

        # Quando os dois templates estao habilitados, alterna por contato valido.
        template_name, template_header_media, log_base = templates_ativos[
            indice_alternancia % len(templates_ativos)
        ]
        indice_alternancia += 1

        mensagem_texto = MENSAGEM_PADRAO.format(nome=nome)
        mensagem = urllib.parse.quote(mensagem_texto)

        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "template_name": template_name,
            "template_params": {"nome": nome},
            "template_lang": "pt_BR",
            "template_header_media": template_header_media,
            "fallback_template_name": TEMPLATE_REENGAJAMENTO_MARKETING,
            "fallback_template_params": {"nome": nome},
            "log": f"{log_base} - campanha={CAMPANHA_ID}",
        })

        marcar_como_enviado(chave)
        registrar_log(numero, nome, f"{log_base} - campanha={CAMPANHA_ID}")
