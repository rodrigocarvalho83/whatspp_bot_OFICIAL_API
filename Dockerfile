FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Sao_Paulo

WORKDIR /app

# Dependencias basicas de runtime (timezone/certificados)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias Python primeiro para melhor cache de build
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copia o codigo da aplicacao
COPY . /app

# Garante diretorios persistidos por volume
RUN mkdir -p /app/log /app/contatos_enviados

CMD ["python", "main.py"]

