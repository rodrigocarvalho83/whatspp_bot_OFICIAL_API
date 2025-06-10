from selenium import webdriver
import chromedriver_autoinstaller
import time

options = webdriver.ChromeOptions()
options.add_argument("user-data-dir=C:/Users/rodri/AppData/Local/Google/Chrome/User Data/whatsapp-profile-bot")
options.add_experimental_option("detach", True)
# options.add_argument("--headless=new")  # Desativado para ver o navegador
options.add_argument("--remote-debugging-port=9222")
chromedriver_autoinstaller.install()

driver = webdriver.Chrome(options=options)

# AQUI TESTAMOS O NAVEGADOR DIRETAMENTE
driver.get("https://web.whatsapp.com/")

# Espera manual para ver se o site carrega
time.sleep(30)
