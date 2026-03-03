import os, re
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Query
import fdb

TZ_SP = timezone(timedelta(hours=-3))  # America/Sao_Paulo

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

app = FastAPI()

@app.get("/orders")
def get_orders(
    start: str = Query(..., description="ISO datetime, ex: 2026-03-02T00:00:00-03:00"),
    end: str = Query(..., description="ISO datetime, ex: 2026-03-03T00:00:00-03:00"),
):
    dsn = os.environ["FIREBIRD_DSN"]
    user = os.environ.get("FIREBIRD_USER", "SYSDBA")
    pwd  = os.environ["FIREBIRD_PASSWORD"]

    start_dt = datetime.fromisoformat(start)
    end_dt   = datetime.fromisoformat(end)

    con = fdb.connect(dsn=dsn, user=user, password=pwd, charset="UTF8")
    cur = con.cursor()

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
            "closed_at": datafech.isoformat(),
            "total": float(valortotal) if valortotal is not None else None,
        })

    con.close()
    return out