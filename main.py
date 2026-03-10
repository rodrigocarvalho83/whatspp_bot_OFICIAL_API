# main.py
import time
from modules import disparo_sob_demanda
from utils.message_queue import processar_fila
from core.whatsapp_cloud import WhatsAppCloudAPI
from core.database import executar_consulta, validar_configuracao_banco
import os

# logger.py (ou direto no início do main.py)
import sys
from datetime import datetime

# Importação dinâmica dos módulos
import modules.status_pedido as status_pedido
import modules.satisfacao as satisfacao
import modules.cartao_fidelidade as cartao_fidelidade
import modules.clube_segundopedido as clube_segundopedido
import modules.clube_segundopedido_domingo as clube_segundopedido_domingo
import modules.novos_clientes_1pedido as novos_clientes_1pedido
import modules.recupera_clientes as recupera_clientes
import modules.recomendador_horario as recomendador_horario
import modules.recomendador_habito_30d as recomendador_habito_30d
import modules.disparo_sob_demanda as disparo_sob_demanda
from utils.monitoring import notify

# Adicione seus módulos na ordem desejada aqui
modulos = [
    #("satisfacao", satisfacao),
    #("recomendador_horario", recomendador_horario),

#Módulos já funcionais com WhatsApp API
    ("status_pedido", status_pedido),
    ("recupera_clientes", recupera_clientes),
    ("novos_clientes_1pedido", novos_clientes_1pedido),
    ("disparo_sob_demanda", disparo_sob_demanda),
    ("cartao_fidelidade", cartao_fidelidade),
    ("clube_segundopedido", clube_segundopedido),
    ("clube_segundopedido_domingo", clube_segundopedido_domingo),
    ("recomendador_habito_30d", recomendador_habito_30d),
]

# Metadados de agendamento para módulos com horário fixo.
SCHEDULED_MODULES = {
    "recupera_clientes": {"schedule_type": "fixed_time", "schedule_time": "17:49", "schedule_tz": "America/Sao_Paulo"},
    "novos_clientes_1pedido": {"schedule_type": "fixed_time", "schedule_time": "18:00", "schedule_tz": "America/Sao_Paulo"},
    "clube_segundopedido": {"schedule_type": "fixed_time", "schedule_time": "18:10", "schedule_tz": "America/Sao_Paulo"},
    "clube_segundopedido_domingo": {"schedule_type": "fixed_time", "schedule_time": "18:10", "schedule_tz": "America/Sao_Paulo"},
}

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
    notify("startup", "Bot iniciado")
    cloud_api = WhatsAppCloudAPI()
    dry_run_mode = os.getenv("WHATSAPP_DRY_RUN", "0").strip().lower() in {"1", "true", "sim", "yes"}

    if not cloud_api.esta_configurado() and not dry_run_mode:
        faltando = ", ".join(cloud_api.campos_faltando())
        print("❌ Cloud API não configurada.")
        print(f"Defina as variáveis: {faltando}")
        print("No PowerShell atual, por exemplo:")
        print('$env:WHATSAPP_ACCESS_TOKEN="seu_token"')
        print('$env:WHATSAPP_PHONE_NUMBER_ID="seu_phone_number_id"')
        return
    elif dry_run_mode and not cloud_api.esta_configurado():
        print("🧪 WHATSAPP_DRY_RUN=1 ativo: execução permitida sem credenciais da Cloud API.")

    if dry_run_mode:
        print("🧪 Modo DRY RUN ativo. Nenhuma mensagem será enviada para a API oficial.")
        notify("mode", "Execucao em DRY RUN")
    else:
        print("☁️ Cloud API configurada. Execução 100% via API oficial.")
        notify("mode", "Execucao com envio real")
    try:
        validar_configuracao_banco()
        executar_consulta("SELECT 1 FROM RDB$DATABASE")
        print("Banco validado com sucesso.")
    except Exception as e:
        print("Falha na validacao inicial do banco.")
        print(str(e))
        notify("fatal_error", "Falha na validacao inicial do banco", {"error": str(e)})
        return

    ult_evento_agendado = {}
    try:
        while True:
            for nome, modulo in modulos:
                if modulo.should_run():
                    print(f"⚙️ Executando módulo: {nome} Início da execução: {datetime.now().isoformat()}\n{'='*80}")
                    schedule_meta = SCHEDULED_MODULES.get(nome)
                    if schedule_meta:
                        chave_minuto = datetime.now().strftime("%Y-%m-%d %H:%M")
                        if ult_evento_agendado.get(nome) != chave_minuto:
                            notify(
                                "module_scheduled_run",
                                "Modulo agendado executado",
                                {
                                    "module": nome,
                                    "ran_at": datetime.now().isoformat(),
                                    **schedule_meta,
                                },
                            )
                            ult_evento_agendado[nome] = chave_minuto
                    try:
                        modulo.run(None)
                    except Exception as e:
                        print(f"❌ Erro no módulo {nome}: {e} Horário do erro: {datetime.now().isoformat()}\n{'='*80}")
                        notify(
                            "module_error",
                            f"Erro no modulo {nome}",
                            {"module": nome, "error": str(e)},
                        )
                else:
                    print(f"⏭️ Módulo {nome} ignorado nesta execução. Horário: {datetime.now().isoformat()}\n{'='*80}")
            processar_fila()
            time.sleep(15)  # Intervalo global entre verificações
    except KeyboardInterrupt:
        print(f"🛑 Execução interrompida pelo usuário. Horário: {datetime.now().isoformat()}\n{'='*80}")
        notify("shutdown", "Execucao interrompida pelo usuario")
    except Exception as e:
        notify("fatal_error", "Falha fatal no loop principal", {"error": str(e)})
        raise

if __name__ == "__main__":
    main()
