# core/driver.py
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import os

def _resolver_diretorio_perfil():
    """
    Resolve um diretório de perfil de navegador gravável.

    Prioridade:
    1) WHATSAPP_BROWSER_PROFILE_DIR
    2) LOCALAPPDATA (Windows)
    3) ~/.whatsapp-bot/chrome-profile
    """
    profile_env = os.getenv("WHATSAPP_BROWSER_PROFILE_DIR")
    if profile_env:
        return os.path.abspath(profile_env)

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return os.path.join(local_app_data, "WhatsAppBot", "chrome-profile")

    return os.path.join(os.path.expanduser("~"), ".whatsapp-bot", "chrome-profile")

def iniciar_driver():
    """
    Inicia o WebDriver do Edge com o perfil de usuário configurado.
    Usa webdriver-manager para instalar o EdgeDriver automaticamente.
    """
    options = EdgeOptions()

    # Caminho do perfil do Edge
    user_data_path = _resolver_diretorio_perfil()
    os.makedirs(user_data_path, exist_ok=True)
    options.add_argument(f"user-data-dir={user_data_path}")

    options.add_experimental_option("detach", True)
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--headless=new")


    # Caminho local do driver baixado manualmente
    caminho_driver = "driver/msedgedriver.exe"  # ajuste se necessário
    service = EdgeService(executable_path=caminho_driver)
    
    # Corrigido: usar EdgeService via download automatico
    # service = EdgeService(EdgeChromiumDriverManager().install())

    driver = webdriver.Edge(service=service, options=options)
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