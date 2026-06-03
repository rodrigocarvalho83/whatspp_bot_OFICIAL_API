import argparse
import mimetypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".3gp"}
DOCUMENT_EXTS = {".pdf", ".txt", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}


@dataclass(frozen=True)
class TemplateCase:
    modulo: str
    template: str
    header_type: str | None
    header_url: str | None
    local_path: str | None = None
    observacao: str = ""


def _abs(path):
    return str((ROOT / path).resolve()) if path else None


def _guess_media_type_from_path(path):
    ext = Path(urlparse(path).path).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in DOCUMENT_EXTS:
        return "document"
    return None


def _content_type_to_media_type(content_type):
    value = (content_type or "").split(";")[0].strip().lower()
    if value.startswith("image/"):
        return "image"
    if value.startswith("video/"):
        return "video"
    if value:
        return "document"
    return None


def _bool_env(value):
    return str(value).strip().lower() in {"1", "true", "t", "sim", "s", "yes", "y"}


def montar_casos():
    import modules.cartao_fidelidade as cartao
    import modules.clube_segundopedido as clube
    import modules.clube_segundopedido_domingo as clube_domingo
    import modules.disparo_sob_demanda as demanda
    import modules.novos_clientes_1pedido as novos
    import modules.recupera_clientes as recupera
    import modules.status_pedido as status

    casos = [
        TemplateCase(
            "clube_segundopedido",
            clube.TEMPLATE_SEGUNDO_PEDIDO,
            "image",
            clube.TEMPLATE_HEADER_IMAGE_URL,
            _abs("videos/clube_fimdesemana/teddy_convite.png"),
        ),
        TemplateCase(
            "clube_segundopedido_domingo",
            clube_domingo.TEMPLATE_SEGUNDO_PEDIDO_LEMBRETE,
            "video",
            clube_domingo.TEMPLATE_HEADER_VIDEO_URL,
            _abs("videos/clube_fimdesemana/teddy_ultimato.mp4"),
        ),
    ]

    for template in novos.TEMPLATES_NOVO_CLIENTE_PROMO_48:
        casos.append(
            TemplateCase(
                "novos_clientes_1pedido:promo",
                template,
                "image",
                novos.TEMPLATE_HEADER_IMAGE_PROMO_48,
                _abs("videos/promo/48reais.png"),
            )
        )

    for template in novos.TEMPLATES_NOVO_CLIENTE_CUPOM_20:
        casos.append(
            TemplateCase(
                "novos_clientes_1pedido:cupom",
                template,
                "image",
                novos.TEMPLATE_HEADER_IMAGE_CUPOM_20,
                _abs("videos/promo/teddy_bravo.jpeg"),
            )
        )

    for template in recupera.TEMPLATES_RECUPERA_PROMO_48:
        casos.append(
            TemplateCase(
                "recupera_clientes:promo",
                template,
                "video",
                recupera.TEMPLATE_HEADER_VIDEO_PROMO_48,
                _abs("videos/clube_fimdesemana/teddy_ultimato.mp4"),
            )
        )

    for template in recupera.TEMPLATES_RECUPERA_CUPOM_20:
        casos.append(
            TemplateCase(
                "recupera_clientes:cupom",
                template,
                "video",
                recupera.TEMPLATE_HEADER_VIDEO_CUPOM_20,
                _abs("videos/clube_fimdesemana/teddy_ultimato.mp4"),
            )
        )

    if _bool_env(demanda.HABILITAR_TEMPLATE_IMAGE):
        casos.append(
            TemplateCase(
                "disparo_sob_demanda:image",
                demanda.TEMPLATE_CLIENTES_INATIVOS_IMAGE,
                "image",
                demanda.HEADER_IMAGE_URL,
            )
        )

    if _bool_env(demanda.HABILITAR_TEMPLATE_VIDEO):
        casos.append(
            TemplateCase(
                "disparo_sob_demanda:video",
                demanda.TEMPLATE_CLIENTES_INATIVOS_VIDEO,
                "video",
                demanda.HEADER_VIDEO_URL,
            )
        )

    for pontos in sorted(k for k in cartao.MEDIA_URLS.keys() if isinstance(k, int)):
        template = cartao.TEMPLATE_FIDELIDADE if pontos < 12 else cartao.TEMPLATE_FIDELIDADE_12_PONTOS
        casos.append(
            TemplateCase(
                f"cartao_fidelidade:{pontos}pontos",
                template,
                "image",
                cartao.MEDIA_URLS[pontos],
                _abs(cartao.IMAGENS[pontos]),
            )
        )

    for chave, template in status.TEMPLATES_STATUS.items():
        media = status.MEDIA_URLS_STATUS[chave]
        tipo = "text" if chave == "F" else "video"
        casos.append(
            TemplateCase(
                f"status_pedido:{chave}",
                template,
                None if tipo == "text" else tipo,
                None if tipo == "text" else media,
                _abs(status.VIDEOS[chave]),
                "No modulo, status F envia header_media type=text; a Cloud API ignora esse header."
                if chave == "F"
                else "",
            )
        )

    return casos


def buscar_templates_meta():
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    waba = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "").strip()
    version = os.getenv("WHATSAPP_API_VERSION", "v21.0").strip() or "v21.0"
    timeout = float(os.getenv("WHATSAPP_TIMEOUT", "20"))

    if not token:
        return {}, "WHATSAPP_ACCESS_TOKEN nao configurado."

    headers = {"Authorization": f"Bearer {token}"}
    base = f"https://graph.facebook.com/{version}"

    if not waba:
        if not phone_number_id:
            return {}, "Configure WHATSAPP_BUSINESS_ACCOUNT_ID ou WHATSAPP_PHONE_NUMBER_ID."

        try:
            resp = requests.get(
                f"{base}/{phone_number_id}",
                headers=headers,
                params={"fields": "whatsapp_business_account"},
                timeout=timeout,
            )
            resp.raise_for_status()
            waba = (resp.json().get("whatsapp_business_account") or {}).get("id")
        except requests.HTTPError as exc:
            detalhe = ""
            if exc.response is not None:
                try:
                    detalhe = ((exc.response.json().get("error") or {}).get("message") or "").strip()
                except Exception:
                    detalhe = exc.response.text[:300]
            return {}, (
                "Nao consegui descobrir o WABA ID pelo WHATSAPP_PHONE_NUMBER_ID. "
                "Adicione WHATSAPP_BUSINESS_ACCOUNT_ID no .env"
                + (f" (Meta: {detalhe})" if detalhe else ".")
            )

    if not waba:
        return {}, "WHATSAPP_BUSINESS_ACCOUNT_ID vazio ou invalido."

    templates = {}
    url = f"{base}/{waba}/message_templates"
    params = {"fields": "name,language,status,components", "limit": 100}
    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", []):
            templates[item.get("name")] = item
        url = (data.get("paging") or {}).get("next")
        params = None

    return templates, None


def header_format_meta(template):
    for component in template.get("components") or []:
        if component.get("type") == "HEADER":
            return (component.get("format") or "").strip().lower()
    return None


def validar(casos, templates_meta=None, check_urls=False):
    templates_meta = templates_meta or {}
    resultados = []

    for caso in casos:
        problemas = []
        avisos = []

        if caso.header_type not in {None, "image", "video", "document"}:
            problemas.append(f"header_type invalido: {caso.header_type}")

        if caso.header_url:
            url_type = _guess_media_type_from_path(caso.header_url)
            if url_type and caso.header_type and url_type != caso.header_type:
                problemas.append(f"URL parece {url_type}, mas modulo envia {caso.header_type}")
            if check_urls:
                try:
                    resp = requests.head(caso.header_url, allow_redirects=True, timeout=15)
                    if resp.status_code >= 400:
                        problemas.append(f"URL retornou HTTP {resp.status_code}")
                    content_type = _content_type_to_media_type(resp.headers.get("content-type"))
                    if content_type and caso.header_type and content_type != caso.header_type:
                        problemas.append(
                            f"Content-Type da URL parece {content_type}, mas modulo envia {caso.header_type}"
                        )
                except requests.RequestException as exc:
                    problemas.append(f"Falha ao consultar URL: {exc}")

        if caso.local_path:
            path = Path(caso.local_path)
            local_type = _guess_media_type_from_path(str(path))
            if not path.exists():
                problemas.append(f"arquivo local nao existe: {path}")
            elif local_type is None:
                avisos.append(f"nao reconheci o tipo do arquivo local: {path.name}")
            mime = mimetypes.guess_type(str(path))[0]
            if mime is None:
                avisos.append(f"mimetype local desconhecido: {path.name}")

        meta = templates_meta.get(caso.template)
        if templates_meta and not meta:
            problemas.append("template nao encontrado na Meta")
        elif meta:
            status = meta.get("status")
            if status and status != "APPROVED":
                avisos.append(f"status na Meta: {status}")
            meta_format = header_format_meta(meta)
            if meta_format in {"image", "video", "document"}:
                if caso.header_type != meta_format:
                    problemas.append(f"Meta espera {meta_format}, mas modulo envia {caso.header_type}")
            elif meta_format:
                if caso.header_type:
                    problemas.append(f"Meta espera header {meta_format}, mas modulo envia midia {caso.header_type}")
            elif caso.header_type:
                problemas.append(f"Meta nao tem header de midia, mas modulo envia {caso.header_type}")

        resultados.append((caso, problemas, avisos))

    return resultados


def imprimir(resultados, meta_msg=None):
    total_problemas = 0
    total_avisos = 0
    if meta_msg:
        print(f"AVISO: {meta_msg}")
        print()

    for caso, problemas, avisos in resultados:
        total_problemas += len(problemas)
        total_avisos += len(avisos)
        status = "OK" if not problemas else "ERRO"
        print(f"[{status}] {caso.modulo} -> {caso.template}")
        print(f"      header={caso.header_type or '-'} url={caso.header_url or '-'}")
        if caso.local_path:
            print(f"      local={caso.local_path}")
        if caso.observacao:
            print(f"      obs={caso.observacao}")
        for problema in problemas:
            print(f"      ERRO: {problema}")
        for aviso in avisos:
            print(f"      AVISO: {aviso}")

    print()
    print(f"Resumo: {len(resultados)} casos, {total_problemas} erro(s), {total_avisos} aviso(s).")
    return total_problemas


def main():
    parser = argparse.ArgumentParser(
        description="Valida se os modulos usam midias compativeis com os headers dos templates da Meta."
    )
    parser.add_argument(
        "--meta",
        action="store_true",
        help="Consulta a Graph API e compara com o formato real dos templates aprovados.",
    )
    parser.add_argument(
        "--check-urls",
        action="store_true",
        help="Faz HEAD nas URLs publicas de midia para validar HTTP e Content-Type.",
    )
    args = parser.parse_args()

    templates_meta = {}
    meta_msg = None
    if args.meta:
        try:
            templates_meta, meta_msg = buscar_templates_meta()
        except requests.RequestException as exc:
            meta_msg = f"Falha ao consultar Meta: {exc}"

    resultados = validar(montar_casos(), templates_meta=templates_meta, check_urls=args.check_urls)
    erros = imprimir(resultados, meta_msg=meta_msg)
    raise SystemExit(1 if erros else 0)


if __name__ == "__main__":
    main()
