# whatsapp_mock.py (versão de testes para simular o envio via WhatsApp)
import time

def abrir_conversa(driver, telefone, mensagem):
    print(f"[Mock] abrindo conversa com {telefone} (simulado: Mensagem)")


def enviar_texto(telefone, mensagem):
    print(f"📤 [TESTE] Enviando mensagem para {telefone}:")
    print(mensagem)
    time.sleep(1)  # simula um pequeno delay de envio
    print(f"✅ [TESTE] Mensagem simulada como enviada para {telefone}.")
    return True

def enviar_midia(telefone, mensagem, caminho_arquivo):
    print(f"📤 [TESTE] Enviando mensagem com mídia para {telefone}:")
    print(f"Mensagem: {mensagem}")
    print(f"Arquivo de mídia: {caminho_arquivo}")
    time.sleep(1.5)  # simula delay maior
    print(f"✅ [TESTE] Mensagem com mídia simulada como enviada para {telefone}.")
    return True
