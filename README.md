# WhatsApp Bot API (Docker + VPS)

Este projeto executa campanhas de WhatsApp com base em regras de modulos Python.
No ambiente de producao atual:

1. O bot roda em Docker.
2. A leitura do Firebird e feita por API HTTP (`DB_PROVIDER=api`).
3. O envio de mensagens e feito pela WhatsApp Cloud API.
4. O monitoramento e feito por webhook no n8n (com opcao de alertas no Discord).

## Visao Rapida Da Arquitetura

1. `main.py` executa os modulos periodicamente.
2. Cada modulo consulta dados via `core/database.py`.
3. `core/database.py` chama a API de banco (`/query/select`) quando `DB_PROVIDER=api`.
4. Mensagens entram na fila (`utils/message_queue.py`) e sao enviadas para a Cloud API.
5. Eventos operacionais sao enviados para o n8n por `utils/monitoring.py`.

## Estrutura De Pastas

- `modules/`: regras de negocio e agendamentos.
- `core/`: acesso a banco, API WhatsApp.
- `utils/`: fila, logs, monitoramento.
- `log/`: arquivos de log e fila.
- `contatos_enviados/`: controle de envio.

## Requisitos Minimos

1. Docker e Docker Compose no VPS.
2. Stack Docker ja existente (n8n, postgres, nginx etc).
3. API de banco online (endpoint `/health` e `/query/select`).
4. Credenciais da WhatsApp Cloud API.

## Arquivos Importantes Para Deploy

1. `Dockerfile`
2. `.dockerignore`
3. `.env` (do bot)
4. `docker-compose.yaml` (da stack no VPS)

## Configuracao Do `.env` Do Bot

Use como base o `.env.example`.

### Banco via API (obrigatorio no VPS)

```env
DB_PROVIDER=api
DB_API_BASE_URL=https://vm-api.mrteddypizza.com.br
DB_API_TOKEN=SEU_TOKEN
DB_API_TIMEOUT=20
```

### WhatsApp Cloud API

```env
WHATSAPP_ACCESS_TOKEN=SEU_TOKEN_META
WHATSAPP_PHONE_NUMBER_ID=SEU_PHONE_NUMBER_ID
WHATSAPP_API_VERSION=v21.0
WHATSAPP_TIMEOUT=20
WHATSAPP_CONNECT_TIMEOUT=5
WHATSAPP_READ_TIMEOUT=20
```

### Modos De Execucao

```env
WHATSAPP_DRY_RUN=1
WHATSAPP_TEST_NUMBER=55DDDNXXXXXXXX
```

Regras:

1. `WHATSAPP_DRY_RUN=1`: nao envia de verdade.
2. `WHATSAPP_DRY_RUN=0`: envia de verdade.
3. `WHATSAPP_TEST_NUMBER`: redireciona tudo para numero de teste.

### Monitoramento (n8n)

```env
MONITORING_ENABLED=1
MONITORING_WEBHOOK_URL=https://teddybot.mrteddypizza.com.br/webhook/teddy_bot
MONITORING_TIMEOUT=5
MONITORING_SERVICE_NAME=whatsapp-bot
MONITORING_ENV=production
```

## Bloco Do Servico No `docker-compose.yaml`

Exemplo de servico do bot:

```yaml
whatsapp-bot:
  build:
    context: ./whatsapp-bot_API
    dockerfile: Dockerfile
  container_name: mrteddy-whatsapp-bot
  restart: unless-stopped
  env_file:
    - ./whatsapp-bot_API/.env
  environment:
    TZ: America/Sao_Paulo
  volumes:
    - ./whatsapp-bot_API/log:/app/log
    - ./whatsapp-bot_API/contatos_enviados:/app/contatos_enviados
  command: ["python", "main.py"]
  networks:
    - internal
```

Importante:

1. Evite duplicar `DB_API_*` em `environment` com `${...}` vazio.
2. Se usar `env_file`, mantenha variaveis do banco nele para evitar sobrescrita acidental.

## Passo A Passo De Deploy No VPS

### 1) Copiar projeto

Copie a pasta do bot para o servidor, por exemplo:

```bash
/opt/mrteddy/whatsapp-bot_API
```

### 2) Revisar `.env`

Preencha o arquivo:

```bash
vim /opt/mrteddy/whatsapp-bot_API/.env
```

### 3) Validar compose

Na pasta da stack (`/opt/mrteddy`):

```bash
docker compose config > /tmp/compose.validado.yml
```

### 4) Subir somente o bot (sem afetar os outros servicos)

```bash
docker compose up -d --no-deps --build whatsapp-bot
```

### 5) Verificar status e logs

```bash
docker compose ps whatsapp-bot
docker compose logs -f --tail=200 whatsapp-bot
```

### 6) Reiniciar somente o bot (quando alterar `.env`)

```bash
docker compose up -d --no-deps --force-recreate whatsapp-bot
```

## Validacao Funcional Antes Da Producao

### Teste da API de banco

No PowerShell local (ou terminal no VPS):

```powershell
$h = @{ Authorization = "Bearer $env:DB_API_TOKEN" }
Invoke-RestMethod -Method Get -Uri "$env:DB_API_BASE_URL/health" -Headers $h
```

```powershell
$body = @{ sql = "SELECT 1 AS TESTE FROM RDB`$DATABASE"; params = @() } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$env:DB_API_BASE_URL/query/select" -Headers $h -Body $body -ContentType "application/json"
```

### Teste rapido do adapter Python

```powershell
python -c "from core.database import executar_consulta; print(executar_consulta('SELECT 1 FROM RDB`$DATABASE'))"
```

### Teste de execucao do bot

1. Configure `WHATSAPP_DRY_RUN=1`.
2. Rode `python main.py` (local) ou veja logs no container (VPS).
3. Confirme que nao ha erro de banco.

## Integracao Com n8n + Discord

### Configurar Webhook no n8n

1. Crie workflow com node `Webhook`.
2. Method: `POST`.
3. Path: `teddy_bot`.
4. Ative o workflow.
5. URL de producao: `https://.../webhook/teddy_bot`.

Observacao importante:

1. `webhook-test` e so para teste manual temporario.
2. Se retornar erro "Did you mean GET?", o node esta configurado como GET e precisa mudar para POST.

### Eventos enviados pelo bot

1. `startup`
2. `mode`
3. `module_error`
4. `fatal_error`
5. `shutdown`
6. `module_scheduled_run` (modulos de horario fixo)

### Fluxo sugerido no n8n

1. `Webhook` -> `Set` (normalizar campos).
2. `Set` -> `Postgres` (gravar evento).
3. `Set` -> `IF` (eventos criticos).
4. `IF true` -> `Discord`.

## DDL Sugerido Para Persistir Eventos No Postgres

```sql
CREATE SCHEMA IF NOT EXISTS observability;

CREATE TABLE IF NOT EXISTS observability.bot_events (
  id                BIGSERIAL PRIMARY KEY,
  received_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  event_timestamp   TIMESTAMPTZ NULL,
  service           TEXT NOT NULL,
  environment       TEXT NOT NULL,
  event             TEXT NOT NULL,
  message           TEXT NOT NULL,
  extra             JSONB NOT NULL DEFAULT '{}'::jsonb,
  headers           JSONB NOT NULL DEFAULT '{}'::jsonb,
  query_params      JSONB NOT NULL DEFAULT '{}'::jsonb,
  route_params      JSONB NOT NULL DEFAULT '{}'::jsonb,
  raw_body          JSONB NOT NULL DEFAULT '{}'::jsonb,
  webhook_url       TEXT NULL,
  execution_mode    TEXT NULL,
  source_ip         TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_bot_events_received_at
  ON observability.bot_events (received_at DESC);

CREATE INDEX IF NOT EXISTS idx_bot_events_event
  ON observability.bot_events (event);
```

## Comandos Docker Mais Usados (Operacao Diaria)

```bash
# status
docker compose ps

# logs do bot
docker compose logs -f --tail=200 whatsapp-bot

# rebuild e subir somente bot
docker compose up -d --no-deps --build whatsapp-bot

# restart somente bot
docker compose restart whatsapp-bot

# entrar no container
docker compose exec whatsapp-bot sh

# ver variaveis dentro do container
docker compose exec whatsapp-bot env | grep -E "DB_PROVIDER|DB_API_BASE_URL|DB_API_TOKEN|MONITORING_"
```

## Troubleshooting Rapido

### Erro: `DB_API_BASE_URL nao configurada para DB_PROVIDER=api`

Causa comum: variavel vazia dentro do container.

Passos:

1. `docker compose exec whatsapp-bot env | grep DB_API_BASE_URL`
2. Revisar `.env` da stack e/ou `env_file`.
3. Recriar container:
   `docker compose up -d --no-deps --force-recreate whatsapp-bot`

### Erro no n8n: webhook nao registrado para POST

1. Trocar method do node para `POST`.
2. Ativar workflow.
3. Usar URL de producao `/webhook/...`.

### Mensagens nao chegam

1. Validar `WHATSAPP_DRY_RUN`.
2. Validar `WHATSAPP_TEST_NUMBER`.
3. Conferir logs do bot e resposta da Cloud API.

## Agendamentos Fixos Atuais

1. `recupera_clientes`: `17:49` (exceto segunda).
2. `novos_clientes_1pedido`: `18:00` (exceto segunda).
3. `clube_segundopedido`: sexta `18:10`.
4. `clube_segundopedido_domingo`: domingo `18:10`.

## Seguranca

1. Nunca versionar token real em git.
2. Rotacionar token da API e da Meta periodicamente.
3. Restringir acesso da API de banco por rede/IP quando possivel.
