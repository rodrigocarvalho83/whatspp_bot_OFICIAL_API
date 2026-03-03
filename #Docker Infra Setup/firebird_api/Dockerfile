FROM python:3.11-slim

WORKDIR /app

# instala libfbclient (cliente Firebird) + deps
RUN apt-get update \
  && apt-get install -y --no-install-recommends firebird3.0-utils libfbclient2 ca-certificates \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn fdb

COPY app.py /app/app.py

ENV FIREBIRD_CLIENT=/usr/lib/x86_64-linux-gnu/libfbclient.so.2

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8088"]