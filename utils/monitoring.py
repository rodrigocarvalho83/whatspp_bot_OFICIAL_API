import os
from datetime import datetime, timezone, timedelta

import requests


TZ_SP = timezone(timedelta(hours=-3))


def _enabled() -> bool:
    return os.getenv("MONITORING_ENABLED", "0").strip().lower() in {"1", "true", "sim", "yes"}


def _webhook_url() -> str:
    return os.getenv("MONITORING_WEBHOOK_URL", "").strip()


def _timeout() -> float:
    return float(os.getenv("MONITORING_TIMEOUT", "5"))


def notify(event: str, message: str, extra: dict | None = None) -> None:
    if not _enabled():
        return

    url = _webhook_url()
    if not url:
        return

    payload = {
        "service": os.getenv("MONITORING_SERVICE_NAME", "whatsapp-bot"),
        "environment": os.getenv("MONITORING_ENV", "production"),
        "event": event,
        "message": message,
        "timestamp": datetime.now(TZ_SP).isoformat(),
        "extra": extra or {},
    }

    try:
        requests.post(url, json=payload, timeout=_timeout())
    except Exception:
        # Monitoramento nunca deve quebrar o fluxo principal do bot.
        return

