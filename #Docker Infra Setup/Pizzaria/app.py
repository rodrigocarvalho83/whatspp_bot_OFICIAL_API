import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Optional

import fdb
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

load_dotenv()

TZ_SP = timezone(timedelta(hours=-3))  # America/Sao_Paulo

app = FastAPI(title="VM API Firebird", version="2.1.0")

API_TOKEN = os.getenv("API_TOKEN", "")
FIREBIRD_HOST = os.getenv("FIREBIRD_HOST", "127.0.0.1")
FIREBIRD_PORT = int(os.getenv("FIREBIRD_PORT", "3050"))
FIREBIRD_DATABASE = os.getenv("FIREBIRD_DATABASE", "")
FIREBIRD_USER = os.getenv("FIREBIRD_USER", "SYSDBA")
FIREBIRD_PASSWORD = os.getenv("FIREBIRD_PASSWORD", "masterkey")


class QueryRequest(BaseModel):
    sql: str
    params: Optional[List[Any]] = None


def normalize_phone(raw: str) -> str | None:
    if not raw:
        return None

    digits = re.sub(r"\D+", "", raw)

    # regra do Rodrigo
    if len(digits) < 9:
        return None
    if len(digits) == 9:
        return "5511" + digits
    if len(digits) == 11:
        return "55" + digits

    return None  # descarta 10, 12, 13 etc.


def check_auth(authorization: Optional[str]) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.replace("Bearer ", "").strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


def get_connection():
    dsn = f"{FIREBIRD_HOST}/{FIREBIRD_PORT}:{FIREBIRD_DATABASE}"
    return fdb.connect(
        dsn=dsn,
        user=FIREBIRD_USER,
        password=FIREBIRD_PASSWORD,
        charset="UTF8",
    )


def convert_param(value: Any) -> Any:
    """
    Converte parâmetros vindos do Grafana/HTTP para tipos que o Firebird entende melhor.
    Ex.: '2026-02-01T00:00:00.000Z' -> datetime naive em horário de São Paulo.
    """
    if isinstance(value, str):
        s = value.strip()

        # Grafana costuma mandar timestamps ISO terminando com Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(s)

            # Se vier timezone-aware, converte para São Paulo e remove tzinfo
            if dt.tzinfo is not None:
                dt = dt.astimezone(TZ_SP).replace(tzinfo=None)

            return dt
        except ValueError:
            return value

    return value


def serialize_value(v: Any) -> Any:
    """
    Garante que a resposta seja serializável em JSON.
    """
    if isinstance(v, Decimal):
        return float(v)

    if isinstance(v, (datetime, date)):
        return v.isoformat()

    return v


@app.get("/health")
def health():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM RDB$DATABASE")
        row = cur.fetchone()
        cur.close()
        conn.close()

        return {"status": "ok", "db": row[0] if row else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders")
def get_orders(
    start: str = Query(..., description="ISO datetime, ex: 2026-03-02T00:00:00-03:00"),
    end: str = Query(..., description="ISO datetime, ex: 2026-03-03T00:00:00-03:00"),
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)

    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid start/end datetime: {e}")

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        sql = """
          SELECT
            p.CODIGO,
            p.DATAFECHAMENTO,
            p.VALORTOTAL,
            c.FONEPRINCIPAL
          FROM PEDIDOS p
          JOIN CONTATOS c ON c.CODIGO = p.CODIGOCONTATOCLIENTE
          WHERE p.DATAFECHAMENTO >= ?
            AND p.DATAFECHAMENTO < ?
            AND p.DATAFECHAMENTO IS NOT NULL
            AND c.FONEPRINCIPAL IS NOT NULL
        """

        cur.execute(sql, (start_dt, end_dt))

        out = []
        for codigo, datafech, valortotal, fone in cur.fetchall():
            phone = normalize_phone(fone)
            if not phone:
                continue

            if isinstance(datafech, datetime) and datafech.tzinfo is None:
                datafech = datafech.replace(tzinfo=TZ_SP)

            out.append({
                "order_id": str(codigo),
                "phone_e164": phone,
                "closed_at": datafech.isoformat() if isinstance(datafech, datetime) else None,
                "total": float(valortotal) if valortotal is not None else None,
            })

        return out

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.post("/query/select")
def query_select(
    request: QueryRequest,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        safe_params = [convert_param(p) for p in (request.params or [])]

        cur.execute(request.sql, safe_params)

        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall() if cur.description else []

        data = [
            {col: serialize_value(val) for col, val in zip(columns, row)}
            for row in rows
        ]

        return {
            "rows": data,
            "count": len(data),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.post("/query/execute")
def query_execute(
    request: QueryRequest,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        safe_params = [convert_param(p) for p in (request.params or [])]

        cur.execute(request.sql, safe_params)

        affected_rows = cur.rowcount
        conn.commit()

        return {
            "status": "ok",
            "affected_rows": affected_rows,
        }

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()