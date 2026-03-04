# main.py
import time
from utils.message_queue import processar_fila
from core.whatsapp_cloud import WhatsAppCloudAPI
import os

# logger.py (ou direto no início do main.py)
import sys
from datetime import datetime

# Importação dinâmica dos módulos
import modules.status_pedido as status_pedido
import modules.satisfacao as satisfacao
import modules.cartao_fidelidade as cartao_fidelidade
import modules.clube_fimdesemana as clube_fimdesemana
import modules.clube_segundopedido as clube_segundopedido
import modules.clube_segundopedido_domingo as clube_segundopedido_domingo
import modules.promo_48 as promo_48
import modules.novos_clientes_1pedido as novos_clientes_1pedido
import modules.recupera_clientes as recupera_clientes
import modules.recomendador_horario as recomendador_horario

# Adicione seus módulos na ordem desejada aqui
modulos = [
    #("satisfacao", satisfacao),
    #("cartao_fidelidade", cartao_fidelidade),
    #("clube_segundopedido", clube_segundopedido),
    #("clube_segundopedido_domingo", clube_segundopedido_domingo),
    #("promo_48", promo_48),
    #("clube_fimdesemana", clube_fimdesemana),
    #("recomendador_horario", recomendador_horario),


#Módulos já funcionais com WhatsApp API
    ("status_pedido", status_pedido),
    ("recupera_clientes", recupera_clientes)
    ("novos_clientes_1pedido", novos_clientes_1pedido)
    
    
]

# Configuração da rotação do log
LOG_PATH = "log/execucao.log"
MAX_LOG_SIZE_MB = 50  # Limite máximo de 50MB, altere se desejar

def rotacionar_log():
    if os.path.exists(LOG_PATH):
        size_mb = os.path.getsize(LOG_PATH) / (1024 * 1024)
        if size_mb > MAX_LOG_SIZE_MB:
            os.remove(LOG_PATH)
            print(f"Arquivo {LOG_PATH} removido por atingir {MAX_LOG_SIZE_MB}MB.")

# Classe Tee para duplicar saída no terminal e no log
class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()

def main():
    os.makedirs("log", exist_ok=True)
    rotacionar_log()  # Verifica o tamanho do log e apaga se necessário

    log_file = open(LOG_PATH, "a", encoding="utf-8")
    log_file.write(f"\n\n🕒 Início da execução: {datetime.now().isoformat()}\n{'='*80}\n")

    sys.stdout = Tee(sys.stdout, log_file)
    sys.stderr = Tee(sys.stderr, log_file)

    print("🟢 Iniciando bot de WhatsApp...\n")
    cloud_api = WhatsAppCloudAPI()
    if not cloud_api.esta_configurado():
        faltando = ", ".join(cloud_api.campos_faltando())
        print("❌ Cloud API não configurada.")
        print(f"Defina as variáveis: {faltando}")
        print("No PowerShell atual, por exemplo:")
        print('$env:WHATSAPP_ACCESS_TOKEN="seu_token"')
        print('$env:WHATSAPP_PHONE_NUMBER_ID="seu_phone_number_id"')
        return

    print("☁️ Cloud API configurada. Execução 100% via API oficial.")
    try:
        while True:
            for nome, modulo in modulos:
                if modulo.should_run():
                    print(f"⚙️ Executando módulo: {nome} Início da execução: {datetime.now().isoformat()}\n{'='*80}")
                    try:
                        modulo.run(None)
                    except Exception as e:
                        print(f"❌ Erro no módulo {nome}: {e} Horário do erro: {datetime.now().isoformat()}\n{'='*80}")
                else:
                    print(f"⏭️ Módulo {nome} ignorado nesta execução. Horário: {datetime.now().isoformat()}\n{'='*80}")
            processar_fila()
            time.sleep(15)  # Intervalo global entre verificações
    except KeyboardInterrupt:
        print(f"🛑 Execução interrompida pelo usuário. Horário: {datetime.now().isoformat()}\n{'='*80}")

if __name__ == "__main__":
    main()