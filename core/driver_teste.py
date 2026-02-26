# core/driver.py
from selenium import webdriver
import chromedriver_autoinstaller
import os
import time

def iniciar_driver():
    print(f"📤 [TESTE]Abrindo WhatsApp")
    time.sleep(1)  # simula um pequeno delay de envio
    print(f"✅ [TESTE] Conectado ao Whatsapp Web")
    return True

def finalizar_driver(driver):
    print(f"✅ [TESTE] Finalizado Driver")
    return True
