import os
import mimetypes
from urllib.parse import unquote
from dotenv import load_dotenv

import requests

load_dotenv()

class WhatsAppCloudAPI:
    def __init__(self):
        self.refresh_config()

    def refresh_config(self):
        self.token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        self.version = os.getenv("WHATSAPP_API_VERSION", "v21.0").strip() or "v21.0"
        self.timeout = int(os.getenv("WHATSAPP_TIMEOUT", "30"))

    def esta_configurado(self):
        self.refresh_config()
        return bool(self.token and self.phone_number_id)

    def campos_faltando(self):
        faltando = []
        if not self.token:
            faltando.append("WHATSAPP_ACCESS_TOKEN")
        if not self.phone_number_id:
            faltando.append("WHATSAPP_PHONE_NUMBER_ID")
        return faltando

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    @property
    def _base_url(self):
        return f"https://graph.facebook.com/{self.version}/{self.phone_number_id}"

    def enviar_texto(self, numero, mensagem_codificada):
        mensagem = unquote(mensagem_codificada)
        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"preview_url": False, "body": mensagem},
        }
        resp = requests.post(
            f"{self._base_url}/messages",
            headers=self._headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("messages"):
            raise RuntimeError(f"Resposta inesperada da Cloud API: {body}")
        return body

    def _upload_midia(self, caminho_arquivo):
        mime_type = mimetypes.guess_type(caminho_arquivo)[0] or "application/octet-stream"
        with open(caminho_arquivo, "rb") as arquivo:
            files = {
                "file": (os.path.basename(caminho_arquivo), arquivo, mime_type),
            }
            data = {
                "messaging_product": "whatsapp",
                "type": mime_type,
            }
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = requests.post(
                f"{self._base_url}/media",
                headers=headers,
                files=files,
                data=data,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            media_id = resp.json().get("id")
            if not media_id:
                raise RuntimeError("Upload de mídia sem id retornado pela Cloud API")
            return media_id

    def enviar_midia(self, numero, caminho_arquivo):
        media_id = self._upload_midia(caminho_arquivo)
        ext = os.path.splitext(caminho_arquivo)[1].lower()

        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            tipo = "image"
        elif ext in {".mp4", ".3gp"}:
            tipo = "video"
        else:
            tipo = "document"

        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": tipo,
            tipo: {"id": media_id},
        }

        resp = requests.post(
            f"{self._base_url}/messages",
            headers=self._headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("messages"):
            raise RuntimeError(f"Resposta inesperada da Cloud API: {body}")
        return body

    def enviar_template(self, numero, nome_template, parametros=None, idioma="pt_BR"):
        componentes = []
        if parametros:
            componentes.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(valor)} for valor in parametros],
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "template",
            "template": {
                "name": nome_template,
                "language": {"code": idioma},
            },
        }
        if componentes:
            payload["template"]["components"] = componentes

        resp = requests.post(
            f"{self._base_url}/messages",
            headers=self._headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("messages"):
            raise RuntimeError(f"Resposta inesperada da Cloud API (template): {body}")
        return body