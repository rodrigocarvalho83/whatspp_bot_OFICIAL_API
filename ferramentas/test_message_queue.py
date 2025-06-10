# NÃO FUNCIONA
# ferramentas/test_message_queue.py
import threading
import time
import pytest
import sys
from unittest.mock import patch

# Garante que o diretório raiz seja encontrado para os imports funcionarem
sys.path.append(".")

from utils.message_queue import adicionar_na_fila, processar_fila


class DummyDriver:
    def __init__(self):
        pass

    def get(self, url):
        return True

    def find_elements(self, *args, **kwargs):
        return [True]

    def send_keys(self, *args, **kwargs):
        pass

    def click(self):
        pass


def simular_modulo(modulo_nome, delay, quantidade):
    for i in range(quantidade):
        numero = f"551199999{delay + i:04d}"
        nome = f"{modulo_nome}_Cliente_{i}"
        mensagem = f"Mensagem do módulo {modulo_nome} para {nome}"
        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": None,
            "log": f"Mensagem de {modulo_nome} adicionada"
        })
        time.sleep(0.1)


@pytest.fixture
def driver_mock():
    return DummyDriver()


def test_concorrencia_na_fila(driver_mock):
    print("\n🧪 Iniciando teste de concorrência com múltiplos produtores e consumidor...")

    threads = [
        threading.Thread(target=simular_modulo, args=("status_pedido", 0, 3)),
        threading.Thread(target=simular_modulo, args=("satisfacao", 100, 3)),
        threading.Thread(target=simular_modulo, args=("aniversario", 200, 3)),
        threading.Thread(target=processar_fila, args=(driver_mock,))
    ]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Verifica se a fila foi esvaziada corretamente
    if adicionar_na_fila.queue.qsize() > 0:
        pytest.fail("❌ A fila não foi completamente esvaziada!")

    print("✅ Teste de concorrência finalizado.")
