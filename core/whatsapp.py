# /core/whatsapp.py
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def abrir_conversa(driver, telefone, mensagem):
    #link = f"https://web.whatsapp.com/send?phone={telefone}&text={mensagem}"
    link = f"https://web.whatsapp.com/send?phone=+5511984896954&text={mensagem}"
    driver.get(link)

    # Espera até a interface carregar
    while len(driver.find_elements(By.ID, 'side')) < 1:
        time.sleep(5)

    # Verifica se há erro de número inválido
    time.sleep(5)
    try:
        erro = driver.find_element(By.XPATH, '//div[contains(@data-testid, "alert") or contains(@class, "copyable-text")]')
        if "inválido" in erro.text.lower() or "não tem uma conta" in erro.text.lower():
            print(f"❌ Número inválido ou não possui WhatsApp: {telefone}")
            return False
    except NoSuchElementException:
        pass  # Nenhuma mensagem de erro visível

    return True

def enviar_texto(driver):
    try:
        input_box = driver.find_element(By.XPATH, '//*[@id="main"]/footer//p')
        input_box.send_keys(Keys.ENTER)
        time.sleep(5)
        return True
    except NoSuchElementException:
        print("❌ Campo de mensagem não encontrado.")
        return False

def enviar_midia(driver, caminho_arquivo):
    try:
        # Botão de clipe (ícone de anexar) -> '//*[@id="main"]/footer/div[1]/div/span/div/div[1]/div/button'
        print("⏳ Procurando botão de clipe (Anexar)...")
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/footer/div[1]/div/span/div/div[1]/div/button'))
        ).click()
        print("✅ Botão de Anexar clicado.")

        # Input de upload de vídeo/imagem (após abrir clipe) -> '//*[@id="app"]/div/span[6]/div/ul/div/div/div[2]/li/div/input'
        WebDriverWait(driver, 7).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div/span[6]/div/ul/div/div/div[2]/li/div/input'))
        ).send_keys(caminho_arquivo)
        print("✅ Mídia carregada.")

        # Botão de enviar mídia (ícone de avião) -> '//*[@id="app"]/div/div[3]/div/div[2]/div[2]/span/div/div/div/div[2]/div/div[2]/div[2]/div/div/span'
        WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="app"]/div/div[3]/div/div[2]/div[2]/span/div/div/div/div[2]/div/div[2]/div[2]/div/div/span'))
        ).click()
        print("✅ Botão de Enviar clicado.")

        time.sleep(5)
        return True

    except Exception as e:
        print("❌ Erro ao anexar mídia.")
        print("📄 Dump da página:")
        with open("dump_midia.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"📂 HTML salvo em dump_midia.html")
        print(f"💥 Detalhe do erro: {e}")
        return False
