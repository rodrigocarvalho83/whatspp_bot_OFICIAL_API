# 📦 Projeto: WhatsApp Bot para Pizzaria

Este projeto é um bot modular em Python que automatiza o envio de mensagens via WhatsApp Web usando Selenium. Ele se conecta a um banco de dados Firebird para extrair dados de clientes e envia mensagens personalizadas com base em regras definidas por módulos independentes.

---

## 🔧 Funcionalidades

- Envio automatizado de mensagens via WhatsApp Web
- Envio de texto e vídeo com base no status do pedido
- Conexão com banco Firebird para leitura de dados
- Estrutura modular para diferentes campanhas (ex: satisfação, status do pedido)
- Controle de envio por telefone (via JSON de log) e logs detalhados
- Permite testes com dados fictícios via `ferramentas/teste_status.py`

---

## 🗂 Estrutura de Módulos

Cada módulo em `modules/` define:
- Quando deve rodar (`should_run()`)
- Qual lógica aplicar e mensagem enviar (`run(driver)`)

Outros diretórios:

- `core/`: Funções centrais (driver, WhatsApp, conexão com DB)
- `utils/`: Funções auxiliares (logs, validações, horários)
- `ferramentas/`: Scripts de teste e utilitários
- `videos/`: Mídias para envio no WhatsApp

---

## ▶️ Como usar

1. Clone este repositório:
   ```bash
   git clone https://github.com/seu-usuario/whatsapp-bot.git
   cd whatsapp-bot
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. (Windows) Execute o script de setup se desejar:
   ```bash
   setup_ambiente.bat
   ```

4. Inicie o bot:
   ```bash
   python main.py
   ```

---

## 🧪 Testes

Você pode testar os módulos com dados fictícios usando os scripts da pasta `ferramentas/`. Por exemplo, para testar o envio de status de pedidos:

```bash
python ferramentas/teste_status.py
```

Esse script simula o envio de mensagens e vídeos para números fictícios sem acessar o banco real.

---

## 📅 Agendamento

- O bot pode ser agendado com `cron` ou `Task Scheduler` do Windows.
- O módulo `satisfacao` está configurado para rodar todos os dias às 11:50.

---

## ✅ Requisitos

- Python 3.9+
- Google Chrome instalado
- WebDriver compatível com sua versão do Chrome
- Banco de dados Firebird acessível
- WhatsApp Web autenticado no Chrome da máquina local

---

## ⚠️ Avisos

- O WhatsApp Web precisa estar autenticado para o envio funcionar
- Evite executar múltiplas instâncias do bot ao mesmo tempo
- Arquivos de log e controle de envio ficam salvos na raiz do projeto (`log_status.json`, `log_satisfacao.csv`, etc.)

---

Feito com ❤️ para automatizar o atendimento da pizzaria Mr. Teddy 🍕  
Ajuda um urso, e ganhe sorrisos de volta 🐻
