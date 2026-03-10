import os
from typing import Any, Iterable

import requests
from dotenv import load_dotenv

load_dotenv()

_PLACEHOLDER_TOKENS = {
    "",
    "TOKEN_SUPER_FORTE",
    "SEU_TOKEN",
    "YOUR_TOKEN",
    "CHANGE_ME",
}


class DatabaseAPIConfigError(RuntimeError):
    pass


class DatabaseAPIRequestError(RuntimeError):
    pass


def _provider() -> str:
    return os.getenv("DB_PROVIDER", "firebird").strip().lower()


def validar_configuracao_banco() -> None:
    if _provider() != "api":
        return

    base_url = os.getenv("DB_API_BASE_URL", "").strip().rstrip("/")
    token = os.getenv("DB_API_TOKEN", "").strip()

    if not base_url:
        raise DatabaseAPIConfigError("DB_API_BASE_URL nao configurada para DB_PROVIDER=api")
    if token in _PLACEHOLDER_TOKENS:
        raise DatabaseAPIConfigError(
            "DB_API_TOKEN invalido para DB_PROVIDER=api. "
            "O valor atual parece ser placeholder (ex.: TOKEN_SUPER_FORTE)."
        )


def _executar_consulta_firebird(sql: str, params: Iterable[Any] | None = None):
    # Import tardio para permitir rodar em modo API sem dependencia do fdb.
    import fdb

    conn = fdb.connect(
        host=os.getenv("FIREBIRD_HOST", "localhost"),
        database=os.getenv(
            "FIREBIRD_DATABASE",
            "C:/Users/rodri/AppData/Local/RAL Tecnologia/CreateInstall/CONSUMER.FDB",
        ),
        user=os.getenv("FIREBIRD_USER", "SYSDBA"),
        password=os.getenv("FIREBIRD_PASSWORD", "masterkey"),
    )
    cur = conn.cursor()
    try:
        cur.execute(sql, list(params or []))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def _executar_consulta_api(sql: str, params: Iterable[Any] | None = None):
    base_url = os.getenv("DB_API_BASE_URL", "").rstrip("/")
    token = os.getenv("DB_API_TOKEN", "").strip()
    timeout = float(os.getenv("DB_API_TIMEOUT", "20"))

    if not base_url:
        raise DatabaseAPIConfigError("DB_API_BASE_URL nao configurada para DB_PROVIDER=api")
    if token in _PLACEHOLDER_TOKENS:
        raise DatabaseAPIConfigError(
            "DB_API_TOKEN invalido para DB_PROVIDER=api. "
            "Defina o token real da API de banco no ambiente/container."
        )

    try:
        resp = requests.post(
            f"{base_url}/query/select",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "sql": sql,
                "params": list(params or []),
            },
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        detalhe = ""
        try:
            body = resp.json()
            detalhe = body.get("detail") or body
        except ValueError:
            detalhe = resp.text.strip()

        status = exc.response.status_code if exc.response is not None else "desconhecido"
        raise DatabaseAPIRequestError(
            f"Falha ao consultar API de banco ({status}) em {base_url}/query/select. "
            f"Detalhe: {detalhe or 'sem resposta detalhada'}"
        ) from exc
    except requests.RequestException as exc:
        raise DatabaseAPIRequestError(
            f"Falha de comunicacao com a API de banco em {base_url}/query/select: {exc}"
        ) from exc

    body = resp.json()
    rows = body.get("rows", [])
    if not isinstance(rows, list):
        raise RuntimeError(f"Resposta inesperada da API de banco: {body}")

    # Compatibilidade com os modulos atuais: lista de tuplas como o fdb retorna.
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append(tuple(row.values()))
        elif isinstance(row, (list, tuple)):
            out.append(tuple(row))
        else:
            raise RuntimeError(f"Linha invalida retornada pela API de banco: {row}")
    return out


def executar_consulta(sql: str, params: Iterable[Any] | None = None):
    if _provider() == "api":
        return _executar_consulta_api(sql, params=params)
    return _executar_consulta_firebird(sql, params=params)
