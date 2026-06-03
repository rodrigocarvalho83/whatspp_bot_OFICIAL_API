import argparse
import os
import sys
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

load_dotenv(os.path.join(ROOT, ".env"))

from core.whatsapp_cloud import WhatsAppCloudAPI
import modules.cartao_fidelidade as cartao
import modules.clube_segundopedido as clube
import modules.clube_segundopedido_domingo as clube_domingo
import modules.disparo_sob_demanda as demanda
import modules.novos_clientes_1pedido as novos
import modules.recupera_clientes as recupera
import modules.recomendador_habito_30d as habito
import modules.recomendador_horario as horario
import modules.satisfacao as satisfacao
import modules.status_pedido as status_pedido


@dataclass(frozen=True)
class EnvioTeste:
    modulo: str
    template: str
    params: dict
    header_media: dict | None = None
    idioma: str = "pt_BR"


def _primeiro(lista):
    return lista[0] if lista else None


def montar_envios(nome):
    return [
        EnvioTeste(
            "clube_segundopedido",
            clube.TEMPLATE_SEGUNDO_PEDIDO,
            {"nome": nome},
            {"type": "image", "link": clube.TEMPLATE_HEADER_IMAGE_URL},
        ),
        EnvioTeste(
            "clube_segundopedido_domingo",
            clube_domingo.TEMPLATE_SEGUNDO_PEDIDO_LEMBRETE,
            {"nome": nome},
            {"type": "video", "link": clube_domingo.TEMPLATE_HEADER_VIDEO_URL},
        ),
        EnvioTeste(
            "cartao_fidelidade",
            cartao.TEMPLATE_FIDELIDADE,
            {"nome": nome, "saldoatual": "5"},
            {"type": "image", "link": cartao.MEDIA_URLS[5]},
        ),
        EnvioTeste(
            "disparo_sob_demanda",
            demanda.TEMPLATE_CLIENTES_INATIVOS_IMAGE,
            {"nome": nome},
            {"type": "image", "link": demanda.HEADER_IMAGE_URL},
        ),
        EnvioTeste(
            "novos_clientes_1pedido",
            _primeiro(novos.TEMPLATES_NOVO_CLIENTE_PROMO_48),
            {"nome": nome},
            {"type": "image", "link": novos.TEMPLATE_HEADER_IMAGE_PROMO_48},
        ),
        EnvioTeste(
            "recupera_clientes",
            _primeiro(recupera.TEMPLATES_RECUPERA_PROMO_48),
            {"nome": nome},
            {"type": "video", "link": recupera.TEMPLATE_HEADER_VIDEO_PROMO_48},
        ),
        EnvioTeste(
            "satisfacao",
            satisfacao.TEMPLATE_SATISFACAO,
            {"nome": nome},
        ),
        EnvioTeste(
            "status_pedido",
            status_pedido.TEMPLATES_STATUS["P"],
            {"nome": nome},
            {"type": "video", "link": status_pedido.MEDIA_URLS_STATUS["P"]},
        ),
        EnvioTeste(
            "recomendador_horario",
            horario.TEMPLATE_RECOMENDADOR_HORARIO,
            {"nome": nome, "produto": "Mussarela", "preco": "53.99"},
        ),
        EnvioTeste(
            "recomendador_habito_30d",
            habito.TEMPLATE_RECOMENDADOR_HABITO,
            {"nome": nome, "produto": "Mussarela"},
            {"type": "image", "link": novos.TEMPLATE_HEADER_IMAGE_PROMO_48},
        ),
    ]


def main():
    parser = argparse.ArgumentParser(description="Envia um template de teste por modulo para um numero.")
    parser.add_argument("--numero", required=True, help="Numero com DDI+DDD, ex.: 5511984896954")
    parser.add_argument("--nome", default="Rodrigo", help="Nome usado nos parametros dos templates")
    parser.add_argument("--delay", type=float, default=5.0, help="Segundos entre envios")
    args = parser.parse_args()

    api = WhatsAppCloudAPI()
    if not api.esta_configurado():
        faltando = ", ".join(api.campos_faltando())
        raise SystemExit(f"Cloud API nao configurada. Faltando: {faltando}")

    envios = montar_envios(args.nome)
    total = len(envios)

    for indice, envio in enumerate(envios, start=1):
        print(f"[{indice}/{total}] Enviando {envio.modulo} -> {envio.template}")
        try:
            resposta = api.enviar_template(
                args.numero,
                envio.template,
                envio.params,
                envio.idioma,
                envio.header_media,
            )
            mensagem = ((resposta or {}).get("messages") or [{}])[0].get("id", "sem-id")
            print(f"OK {envio.modulo}: message_id={mensagem}")
        except requests.HTTPError as exc:
            detalhe = ""
            if exc.response is not None:
                try:
                    detalhe = exc.response.json()
                except Exception:
                    detalhe = exc.response.text
            print(f"ERRO {envio.modulo}: {exc} | detalhe={detalhe}")
        except Exception as exc:
            print(f"ERRO {envio.modulo}: {exc}")

        if indice < total:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
