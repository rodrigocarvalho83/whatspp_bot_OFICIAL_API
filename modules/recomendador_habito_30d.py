from datetime import datetime, timedelta
from itertools import combinations
from collections import Counter
import ftplib
import os
import shutil
import time
import urllib.parse

import pandas as pd
import requests

from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila

try:
    from PIL import Image
except Exception:
    Image = None


ENABLED = os.getenv("WHATSAPP_RECOMENDADOR_HABITO_ENABLED", "0").strip().lower() in {"1", "true", "sim", "yes"}
LOCAL_TEST_MODE = os.getenv("WHATSAPP_RECOMENDADOR_HABITO_TEST_MODE", "1").strip().lower() in {"1", "true", "sim", "yes"}

TEMPLATE_RECOMENDADOR_HABITO = os.getenv(
    "WHATSAPP_TEMPLATE_RECOMENDADOR_HABITO",
    "template_recomendador_habito_30d",
)
TEMPLATE_REENGAJAMENTO_MARKETING = os.getenv("WHATSAPP_TEMPLATE_MARKETING", TEMPLATE_RECOMENDADOR_HABITO)

MIN_PEDIDOS_HABITUAL = int(os.getenv("RECOMENDADOR_MIN_PEDIDOS", "6"))  # > 5 pedidos
INATIVIDADE_DIAS = int(os.getenv("RECOMENDADOR_INATIVIDADE_DIAS", "30"))
JANELA_ANTES_HORAS = int(os.getenv("RECOMENDADOR_JANELA_ANTES_HORAS", "1"))
MAX_CLIENTES_POR_EXECUCAO = int(os.getenv("RECOMENDADOR_MAX_CLIENTES", "50"))

HORA_INICIO = os.getenv("RECOMENDADOR_HORA_INICIO", "11:00")
HORA_FIM = os.getenv("RECOMENDADOR_HORA_FIM", "23:30")

PASTA_FOTOS_PRODUTOS = os.getenv("RECOMENDADOR_FOTOS_DIR", "videos/imagens_pizza")
PASTA_COMBINACOES = os.getenv("RECOMENDADOR_COMBINACOES_DIR", "tmp/combinacoes")
EXT_FOTO = os.getenv("RECOMENDADOR_FOTO_EXT", ".jpg")

PUBLIC_BASE_URL = os.getenv("RECOMENDADOR_PUBLIC_BASE_URL", "https://mrteddypizza.com.br/midia/combinacoes").rstrip("/")
UPLOAD_MODE = os.getenv("RECOMENDADOR_UPLOAD_MODE", "none").strip().lower()  # none|ftp|local_copy
UPLOAD_TIMEOUT_S = int(os.getenv("RECOMENDADOR_UPLOAD_TIMEOUT_S", "20"))
URL_READY_TIMEOUT_S = int(os.getenv("RECOMENDADOR_URL_READY_TIMEOUT_S", "20"))
URL_READY_INTERVAL_S = float(os.getenv("RECOMENDADOR_URL_READY_INTERVAL_S", "2"))

FTP_HOST = os.getenv("RECOMENDADOR_FTP_HOST", "")
FTP_PORT = int(os.getenv("RECOMENDADOR_FTP_PORT", "21"))
FTP_USER = os.getenv("RECOMENDADOR_FTP_USER", "")
FTP_PASS = os.getenv("RECOMENDADOR_FTP_PASS", "")
FTP_DIR = os.getenv("RECOMENDADOR_FTP_DIR", "/")
FTP_SSL = os.getenv("RECOMENDADOR_FTP_SSL", "0").strip().lower() in {"1", "true", "sim", "yes"}

LOCAL_PUBLIC_DIR = os.getenv("RECOMENDADOR_LOCAL_PUBLIC_DIR", "")

ultima_execucao = datetime.min
intervalo_execucao = timedelta(minutes=5)


def should_run():
    global ultima_execucao
    if not ENABLED:
        return False

    agora = datetime.now()
    if agora - ultima_execucao < intervalo_execucao:
        return False

    if not dentro_do_horario():
        return False

    ultima_execucao = agora
    return True


def dentro_do_horario():
    agora = datetime.now().time()
    return HORA_INICIO <= agora.strftime("%H:%M") <= HORA_FIM


def _query_historico():
    return """
        SELECT
            p.CODIGO AS CODIGO_PEDIDO,
            p.DATAABERTURA,
            p.CODIGOCONTATOCLIENTE AS CODIGO_CLIENTE,
            c.NOME AS NOME_CLIENTE,
            c.FONEPRINCIPAL AS TELEFONE,
            COALESCE(pd.CODIGOPRODUTO, i.CODIGOPRODUTO) AS CODIGO_PRODUTO,
            pr.NOME AS NOME_PRODUTO
        FROM PEDIDOS p
        INNER JOIN CONTATOS c ON c.CODIGO = p.CODIGOCONTATOCLIENTE
        INNER JOIN ITENSPEDIDO i ON i.CODIGOPEDIDO = p.CODIGO
        INNER JOIN ITEMPEDIDOTIPO t ON t.CODIGO = i.CODIGOITEMPEDIDOTIPO
        LEFT JOIN PRODUTODETALHE pd ON pd.CODIGO = i.CODIGOPRODUTODETALHE
        LEFT JOIN PRODUTOS pr ON pr.CODIGO = COALESCE(pd.CODIGOPRODUTO, i.CODIGOPRODUTO)
        WHERE p.DATADELETE IS NULL
          AND i.DATADELETE IS NULL
          AND c.DATADELETE IS NULL
          AND t.CODIGO NOT IN (1,2,6)
          AND (pd.CODIGOPRODUTOTAMANHO IS NULL OR pd.CODIGOPRODUTOTAMANHO <> 2)
          AND c.FONEPRINCIPAL IS NOT NULL
          AND TRIM(c.FONEPRINCIPAL) <> ''
        ORDER BY p.DATAABERTURA DESC
    """


def _foto_produto_path(codigo_produto):
    return os.path.abspath(os.path.join(PASTA_FOTOS_PRODUTOS, f"{codigo_produto}{EXT_FOTO}"))


def _escolher_produtos_preferidos(df_cliente):
    freq = df_cliente.groupby("codigoproduto").size().sort_values(ascending=False)
    produto_fallback = int(freq.index[0]) if not freq.empty else None
    nome_fallback = None
    if produto_fallback is not None:
        nomes = df_cliente[df_cliente["codigoproduto"] == produto_fallback]["nome_produto"].dropna()
        nome_fallback = str(nomes.iloc[0]) if not nomes.empty else f"Produto {produto_fallback}"

    pares = Counter()
    for _, pedido_grupo in df_cliente.groupby("codigopedido"):
        produtos_unicos = sorted(set(int(x) for x in pedido_grupo["codigoproduto"].dropna().tolist()))
        for a, b in combinations(produtos_unicos, 2):
            pares[(a, b)] += 1

    if pares:
        (a, b), _ = pares.most_common(1)[0]
        return a, b, produto_fallback, nome_fallback
    return None, None, produto_fallback, nome_fallback


def _gerar_imagem_meio_a_meio(id_esq, id_dir):
    if Image is None:
        raise RuntimeError("Pillow nao instalado. Instale com: pip install pillow")

    origem_esq = _foto_produto_path(id_esq)
    origem_dir = _foto_produto_path(id_dir)
    if not os.path.exists(origem_esq) or not os.path.exists(origem_dir):
        raise FileNotFoundError(f"Foto inexistente para meio a meio: {origem_esq} | {origem_dir}")

    os.makedirs(PASTA_COMBINACOES, exist_ok=True)
    a, b = sorted([int(id_esq), int(id_dir)])
    destino = os.path.abspath(os.path.join(PASTA_COMBINACOES, f"{a}_{b}.jpg"))
    if os.path.exists(destino):
        return destino, f"{a}_{b}.jpg"

    with Image.open(origem_esq).convert("RGB") as img_esq, Image.open(origem_dir).convert("RGB") as img_dir:
        largura = min(img_esq.width, img_dir.width)
        altura = min(img_esq.height, img_dir.height)
        img_esq = img_esq.resize((largura, altura))
        img_dir = img_dir.resize((largura, altura))

        metade = largura // 2
        parte_esq = img_esq.crop((0, 0, metade, altura))
        parte_dir = img_dir.crop((metade, 0, largura, altura))

        final = Image.new("RGB", (largura, altura))
        final.paste(parte_esq, (0, 0))
        final.paste(parte_dir, (metade, 0))
        final.save(destino, format="JPEG", quality=90, optimize=True)

    return destino, f"{a}_{b}.jpg"


def _upload_ftp(caminho_local, nome_arquivo):
    klass = ftplib.FTP_TLS if FTP_SSL else ftplib.FTP
    ftp = klass()
    ftp.connect(FTP_HOST, FTP_PORT, timeout=UPLOAD_TIMEOUT_S)
    ftp.login(FTP_USER, FTP_PASS)
    if FTP_SSL:
        ftp.prot_p()
    if FTP_DIR and FTP_DIR != "/":
        ftp.cwd(FTP_DIR)
    with open(caminho_local, "rb") as f:
        ftp.storbinary(f"STOR {nome_arquivo}", f)
    ftp.quit()


def _upload_local_copy(caminho_local, nome_arquivo):
    if not LOCAL_PUBLIC_DIR:
        raise RuntimeError("RECOMENDADOR_LOCAL_PUBLIC_DIR nao configurado para upload local_copy")
    os.makedirs(LOCAL_PUBLIC_DIR, exist_ok=True)
    shutil.copy2(caminho_local, os.path.join(LOCAL_PUBLIC_DIR, nome_arquivo))


def _garantir_url_publica(caminho_local, nome_arquivo):
    url = f"{PUBLIC_BASE_URL}/{nome_arquivo}"
    if LOCAL_TEST_MODE:
        return f"{url}?v={int(time.time())}"

    if UPLOAD_MODE == "ftp":
        _upload_ftp(caminho_local, nome_arquivo)
    elif UPLOAD_MODE == "local_copy":
        _upload_local_copy(caminho_local, nome_arquivo)
    elif UPLOAD_MODE == "none":
        pass
    else:
        raise RuntimeError(f"RECOMENDADOR_UPLOAD_MODE invalido: {UPLOAD_MODE}")

    if _aguardar_url_disponivel(url):
        return f"{url}?v={int(time.time())}"
    raise RuntimeError(f"URL nao ficou disponivel a tempo: {url}")


def _aguardar_url_disponivel(url):
    inicio = time.time()
    while time.time() - inicio <= URL_READY_TIMEOUT_S:
        try:
            resp = requests.head(url, timeout=5, allow_redirects=True)
            if resp.status_code == 200:
                return True
            if resp.status_code in (403, 405):
                resp_get = requests.get(url, timeout=5, allow_redirects=True)
                if resp_get.status_code == 200:
                    return True
        except Exception:
            pass
        time.sleep(URL_READY_INTERVAL_S)
    return False


def _hora_envio_alvo(hora_habitual):
    return (int(hora_habitual) - JANELA_ANTES_HORAS) % 24


def run(driver):
    resultados = executar_consulta(_query_historico())
    if not resultados:
        return

    colunas = [
        "codigopedido",
        "dataabertura",
        "codigocliente",
        "nome_cliente",
        "telefone",
        "codigoproduto",
        "nome_produto",
    ]
    df = pd.DataFrame(resultados, columns=colunas)
    if df.empty:
        return

    df["dataabertura"] = pd.to_datetime(df["dataabertura"])
    df = df[df["codigocliente"].notna() & df["codigoproduto"].notna()]

    agora = datetime.now()
    limite_inatividade = agora - timedelta(days=INATIVIDADE_DIAS)
    hora_atual = agora.hour

    pedidos_cliente = (
        df[["codigocliente", "codigopedido", "dataabertura"]]
        .drop_duplicates(subset=["codigocliente", "codigopedido"])
    )
    resumo_cliente = pedidos_cliente.groupby("codigocliente").agg(
        qtd_pedidos=("codigopedido", "count"),
        ultimo_pedido=("dataabertura", "max"),
    )
    elegiveis = resumo_cliente[
        (resumo_cliente["qtd_pedidos"] >= MIN_PEDIDOS_HABITUAL) &
        (resumo_cliente["ultimo_pedido"] <= limite_inatividade)
    ]
    if elegiveis.empty:
        print("Recomendador 30d: nenhum cliente elegivel nesta execucao.")
        return

    processados = 0
    for cod_cliente in elegiveis.sort_values("ultimo_pedido").index.tolist():
        df_cliente = df[df["codigocliente"] == cod_cliente].copy()
        if df_cliente.empty:
            continue

        linha_base = df_cliente.iloc[0]
        numero = validar_numero(linha_base["telefone"])
        if not numero:
            continue
        nome = formatar_nome(str(linha_base["nome_cliente"] or "Cliente"))

        horas_cliente = (
            pedidos_cliente[pedidos_cliente["codigocliente"] == cod_cliente]["dataabertura"]
            .dt.hour
            .value_counts()
        )
        if horas_cliente.empty:
            continue
        hora_habitual = int(horas_cliente.index[0])
        hora_alvo = _hora_envio_alvo(hora_habitual)
        if hora_atual != hora_alvo:
            continue

        semana_ref = f"{agora.isocalendar().year}-W{agora.isocalendar().week}"
        chave_envio = f"HABITO30D-{cod_cliente}-{semana_ref}"
        if ja_enviado(chave_envio):
            continue

        meio_a_meio_a, meio_a_meio_b, produto_fallback, nome_fallback = _escolher_produtos_preferidos(df_cliente)
        if produto_fallback is None:
            continue

        header_url = None
        caminho_local = None
        nome_recomendado = nome_fallback or f"Produto {produto_fallback}"

        try:
            if meio_a_meio_a and meio_a_meio_b:
                caminho_local, nome_remoto = _gerar_imagem_meio_a_meio(meio_a_meio_a, meio_a_meio_b)
                header_url = _garantir_url_publica(caminho_local, nome_remoto)
                nome_a = df_cliente[df_cliente["codigoproduto"] == meio_a_meio_a]["nome_produto"].dropna()
                nome_b = df_cliente[df_cliente["codigoproduto"] == meio_a_meio_b]["nome_produto"].dropna()
                if not nome_a.empty and not nome_b.empty:
                    nome_recomendado = f"Meio a meio: {nome_a.iloc[0]} + {nome_b.iloc[0]}"
            else:
                caminho_local = _foto_produto_path(produto_fallback)
                if os.path.exists(caminho_local):
                    header_url = _garantir_url_publica(caminho_local, f"{produto_fallback}{EXT_FOTO}")
        except Exception as e:
            print(f"Recomendador 30d: falha ao preparar imagem do cliente {cod_cliente}: {e}")
            continue

        if not header_url:
            continue

        mensagem_texto = (
            f"{nome}, aqui e o Teddy! "
            f"Bateu vontade da sua pedida favorita de sempre: *{nome_recomendado}*? "
            "Se quiser, ja deixo seu pedido pronto agora."
        )
        mensagem = urllib.parse.quote(mensagem_texto)

        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": caminho_local,
            "template_name": TEMPLATE_RECOMENDADOR_HABITO,
            "template_params": {"nome": nome, "produto": nome_recomendado},
            "template_lang": "pt_BR",
            "template_header_media": {"type": "image", "link": header_url},
            "fallback_template_name": TEMPLATE_REENGAJAMENTO_MARKETING,
            "fallback_template_params": {"nome": nome},
            "log": f"Recomendador 30d (cliente={cod_cliente}, hora_habitual={hora_habitual}, hora_alvo={hora_alvo})",
        })

        marcar_como_enviado(chave_envio)
        registrar_log(numero, nome, f"Recomendador 30d enfileirado (produto={nome_recomendado})")

        processados += 1
        if processados >= MAX_CLIENTES_POR_EXECUCAO:
            break

