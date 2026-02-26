# core/driver.py
from selenium import webdriver
import chromedriver_autoinstaller
import os

def iniciar_driver():
    """
    Inicia o WebDriver do Chrome com o perfil de usuário configurado.
    Garante que o ChromeDriver esteja instalado automaticamente.
    """
    options = webdriver.ChromeOptions()

    # Caminho do perfil do Chrome para manter sessão do WhatsApp Web
    user_data_path = "C:/Users/Apoio1/AppData/Local/Google/Chrome/User Data/whatsapp-profile-bot_definitivo"
    options.add_argument(f"user-data-dir={user_data_path}")

    options.add_experimental_option("detach", True)  # Mantém o navegador aberto após execução
    options.add_argument("--remote-debugging-port=9222")  # Ajuda em conexões estáveis
    options.add_argument("--headless=new")

    # Instala automaticamente o ChromeDriver compatível
    chromedriver_autoinstaller.install()

    # Inicializa o driver com as opções definidas
    driver = webdriver.Chrome(options=options)
    driver.get("https://web.whatsapp.com")

    return driver

def finalizar_driver(driver):
    """
    Finaliza o WebDriver, encerrando o navegador.
    """
    try:
        driver.quit()
    except Exception:
        pass
