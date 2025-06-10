# ferramentas/teste_status.py
import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.driver import iniciar_driver
from core.whatsapp import abrir_conversa, enviar_texto, anexar_midia
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log

# Dados fictícios
pedidos_ficticios = [
    {
        "codigo": 101,
        "nome": "Carlos Silva",
        "telefone": "11999999999",
        "status": "P",
        "endereco": "Rua das Flores",
        "numero": "123"
    },
    {
        "codigo": 102,
        "nome": "Ana Souza",
        "telefone": "11988888888",
        "status": "S",
        "endereco": "Av. Paulista",
        "numero": "1000"
    }
]

mensagens = {
    "P": "Olá {nome}, seu pedido está sendo preparado! Logo estará a caminho. 🍕",
    "S": "Olá {nome}, seu pedido saiu para entrega. Fique de olho! 🚚"
}

videos = {
    "P": "videos/em_preparacao.mp4",
    "S": "videos/saiu_entrega.mp4"
}

driver = iniciar_driver()

for pedido in pedidos_ficticios:
    if ja_enviado(pedido["codigo"]):
        continue

    mensagem = mensagens.get(pedido["status"], "Olá! Seu pedido está em andamento.").format(nome=pedido["nome"])
    caminho_video = os.path.abspath(videos.get(pedido["status"], "videos/status_pedidos/default.MP4"))

    if abrir_conversa(driver, pedido["telefone"], mensagem):
        time.sleep(10)  # Espera carregar o chat
        anexar_midia(driver, caminho_video)
        enviar_texto(driver)
        registrar_log(pedido["telefone"], pedido["nome"], pedido["status"])
        marcar_como_enviado(pedido["codigo"])
        time.sleep(5)

driver.quit()
