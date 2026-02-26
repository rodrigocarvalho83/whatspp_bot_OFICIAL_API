### utils/formatters.py
import re

def limpar_numero(telefone):
    return re.sub(r'\D', '', telefone)

def validar_numero(telefone):
    numero = limpar_numero(telefone)
    # 🚫 Regra de exclusão: números 0800 não devem ser processados
    if numero.startswith('0800'):
        return None
    if len(numero) < 9:
        return None
    if len(numero) == 9:
        numero = '11' + numero
    if len(numero) == 11:
        numero = '55' + numero
    if len(numero) != 13:
        return None
    return numero

def formatar_nome(nome_completo):
    return nome_completo.split()[0].capitalize()

