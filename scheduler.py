### scheduler.py
import time
import importlib
import os

def carregar_modulos():
    modulos = []
    for arquivo in os.listdir('modules'):
        if arquivo.endswith('.py') and not arquivo.startswith('__'):
            nome_modulo = f"modules.{arquivo[:-3]}"
            modulos.append(importlib.import_module(nome_modulo))
    return modulos

def loop_agendador():
    modulos = carregar_modulos()

    while True:
        for modulo in modulos:
            try:
                if modulo.should_run():
                    print(f"Executando módulo: {modulo.__name__}")
                    modulo.run(None)
            except Exception as e:
                print(f"Erro no módulo {modulo.__name__}: {e}")
        time.sleep(60)
