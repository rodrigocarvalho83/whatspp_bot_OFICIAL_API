from datetime import datetime
import os
import urllib.parse

from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila

# =========================
# CONFIGURACOES DO DISPARO
# =========================
# Defina os nomes dos templates aprovados na Meta.
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

# Habilita/desabilita cada template no disparo.
# Valores aceitos: 1/0, true/false, sim/nao, yes/no.
HABILITAR_TEMPLATE_IMAGE = os.getenv(
    "WHATSAPP_SOB_DEMANDA_HABILITAR_TEMPLATE_IMAGE",
    "1",
).strip()
HABILITAR_TEMPLATE_VIDEO = os.getenv(
    "WHATSAPP_SOB_DEMANDA_HABILITAR_TEMPLATE_VIDEO",
    "0",
).strip()

# URLs de header para os templates (placeholders iniciais).
# Troque para a URL real da imagem/video antes de disparar.
HEADER_IMAGE_URL = os.getenv(
    "WHATSAPP_SOB_DEMANDA_HEADER_IMAGE_URL",
    "https://mrteddypizza.com.br/midia/promo/48reais.png",
)
HEADER_VIDEO_URL = os.getenv(
    "WHATSAPP_SOB_DEMANDA_HEADER_VIDEO_URL",
    "https://example.com/placeholder-clientes-inativos-video.mp4",
)

# Agendamento: data e hora exatas em que o modulo pode rodar.
# Data obrigatoria (YYYY-MM-DD). Se ficar vazia, o modulo nao dispara.
DATA_DISPARO = os.getenv("WHATSAPP_SOB_DEMANDA_DATA", "2026-03-04").strip()
# Hora no formato HH:MM.
HORA_DISPARO = os.getenv("WHATSAPP_SOB_DEMANDA_HORA", "17:14").strip()
# Identificador da campanha para controle de duplicidade no status_log.
CAMPANHA_ID = os.getenv("WHATSAPP_SOB_DEMANDA_CAMPANHA_ID", "clientes_inativos").strip()

# Query padrao do disparo sob demanda.
# Edite livremente conforme sua necessidade, mantendo o retorno:
# CODIGO, NOME, FONEPRINCIPAL, DATAINSERT
SQL_SOB_DEMANDA = """
SELECT
    C.CODIGO,
    C.NOME,
    C.FONEPRINCIPAL,
    C.DATAINSERT
FROM CONTATOS C
LEFT JOIN PEDIDOS P
    ON P.CODIGOCONTATOCLIENTE = C.CODIGO
WHERE C.DATADELETE IS NULL
  AND P.CODIGO IS NULL
ORDER BY C.DATAINSERT
"""


def _bool_env(valor):
    return str(valor).strip().lower() in {"1", "true", "t", "sim", "s", "yes", "y"}


def should_run():
    if not DATA_DISPARO:
        return False

    agora = datetime.now()
    return agora.strftime("%Y-%m-%d") == DATA_DISPARO and agora.strftime("%H:%M") == HORA_DISPARO


def _templates_habilitados():
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


def _query_sob_demanda():
    # Opcional: se WHATSAPP_SOB_DEMANDA_SQL for preenchida no ambiente,
    # ela sobrescreve a SQL padrao acima sem precisar editar este arquivo.
    sql_custom = os.getenv("WHATSAPP_SOB_DEMANDA_SQL", "").strip()
    return sql_custom if sql_custom else SQL_SOB_DEMANDA


def run(driver):
    templates_ativos = _templates_habilitados()
    if not templates_ativos:
        print("Nenhum template habilitado no disparo sob demanda.")
        return

    resultados = executar_consulta(_query_sob_demanda())
    data_execucao = datetime.now().strftime("%Y-%m-%d")
    indice_alternancia = 0

    for codigo, nome_raw, telefone_raw, _datainsert in resultados:
        if not nome_raw or not telefone_raw:
            continue

        numero = validar_numero(telefone_raw)
        if not numero:
            continue

        nome = formatar_nome(nome_raw)
        chave = f"SOBDEMANDA-{CAMPANHA_ID}-{data_execucao}-{codigo}-{numero}"
        if ja_enviado(chave):
            continue

        # Se os dois templates estiverem habilitados, alterna entre image/video.
        template_name, template_header_media, log_base = templates_ativos[
            indice_alternancia % len(templates_ativos)
        ]
        indice_alternancia += 1

        mensagem_texto = f"Oi {nome}, temos uma condicao especial para voce."
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
