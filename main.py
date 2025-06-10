# main.py
import time
from core.driver import iniciar_driver
from utils.message_queue import processar_fila

# Importação dinâmica dos módulos
import modules.status_pedido as status_pedido
import modules.satisfacao as satisfacao

modulos = [
    ("status_pedido", status_pedido),
    ("satisfacao", satisfacao)
]

def main():
    print("🟢 Iniciando bot de WhatsApp...\n")
    driver = iniciar_driver()

    try:
        while True:
            for nome, modulo in modulos:
                if modulo.should_run():
                    print(f"⚙️ Executando módulo: {nome}")
                    try:
                        modulo.run(driver)
                    except Exception as e:
                        print(f"❌ Erro no módulo {nome}: {e}")
                else:
                    print(f"⏭️ Módulo {nome} ignorado nesta execução.")
            processar_fila(driver)
            time.sleep(10)  # Intervalo global entre verificações
    except KeyboardInterrupt:
        print("🛑 Execução interrompida pelo usuário.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
