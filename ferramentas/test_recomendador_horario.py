import pandas as pd
from datetime import datetime, timedelta
from collections import Counter
import json
import os

# Simula preços especiais
precos_especiais = {
    "105": 45.00,
    "111": 55.50,
    "127": 50.00
}

# Simula base de dados de pedidos
data = [
    # codigopedido, dataabertura, nome_produto, codigoproduto, precovenda, quantidade, codigocontatocliente, nome, fone, endereco, numero, bairro
    [1, "2024-07-16 18:10", "Calabresa", 105, 60.00, 1, 123, "Rodrigo", "5511912345678", "Rua das Pizzas", "321", "Centro"],
    [2, "2024-07-09 18:15", "Calabresa", 105, 60.00, 1, 123, "Rodrigo", "5511912345678", "Rua das Pizzas", "321", "Centro"],
    [3, "2024-07-02 18:25", "Calabresa", 105, 60.00, 1, 123, "Rodrigo", "5511912345678", "Rua das Pizzas", "321", "Centro"],
    [4, "2024-07-12 19:00", "Mussarela", 127, 54.00, 2, 333, "Amanda", "5511919988777", "Av. Queijo", "101", "Vila Sabor"],
    [5, "2024-07-05 19:05", "Mussarela", 127, 54.00, 1, 333, "Amanda", "5511919988777", "Av. Queijo", "101", "Vila Sabor"],
    [6, "2024-07-19 19:45", "Mussarela", 127, 54.00, 1, 333, "Amanda", "5511919988777", "Av. Queijo", "101", "Vila Sabor"],
]

colunas = [
    "codigopedido", "dataabertura", "nome_produto", "codigoproduto", "precovenda", "quantidade",
    "codigocontatocliente", "nome", "fone", "endereco", "numero", "bairro"
]
df = pd.DataFrame(data, columns=colunas)
df["dataabertura"] = pd.to_datetime(df["dataabertura"])

# Definindo agora (ajuste para simular outros horários!)
agora = datetime(2024, 7, 16, 17, 0)  # 17:00 do dia 16/julho/2024 (terça-feira)
proxima_hora = (agora + timedelta(hours=1)).hour  # 18

clientes_mensagem = []
for codcliente, sub in df.groupby("codigocontatocliente"):
    if sub.shape[0] < 3:
        continue

    sub["hora"] = sub["dataabertura"].dt.hour
    sub["dia_semana"] = sub["dataabertura"].dt.dayofweek  # 0=segunda

    frequencia = Counter(zip(sub["dia_semana"], sub["hora"]))
    (dia_semana, hora), _ = frequencia.most_common(1)[0]

    if hora != proxima_hora or dia_semana != agora.weekday():
        continue

    produto_mais_comum = sub["codigoproduto"].mode()[0]
    linha_produto = sub[sub["codigoproduto"] == produto_mais_comum].iloc[0]
    nome_produto = linha_produto["nome_produto"]
    preco_produto = precos_especiais.get(str(produto_mais_comum), linha_produto["precovenda"])
    foto_produto = f"videos/imagens_pizza/{produto_mais_comum}.jpg"

    nome = linha_produto["nome"]
    numero = linha_produto["fone"]

    endereco = linha_produto["endereco"]
    num_endereco = linha_produto["numero"]
    bairro = linha_produto["bairro"]

    endereco_str = ""
    if endereco and num_endereco and bairro:
        endereco_str = f"{endereco}, {num_endereco}, {bairro}"

    mensagem = (
        f"Olá {nome}! Aqui é o Teddy da Mr. Teddy 🍕🐻\n"
        f"Sabe que a gente te conhece tão bem que já sei o que você normalmente pede nessa hora da {['segunda','terça','quarta','quinta','sexta','sábado','domingo'][dia_semana]}!\n\n"
        f"Quer repetir aquela pizza {nome_produto} hoje? Tá só esperando a sua confirmação pra eu começar a preparar.\n"
    )
    if endereco_str:
        mensagem += f"\nO endereço que tenho aqui é: {endereco_str}\nSe quiser mudar, me avisa!"

    mensagem += (
        f"\n\nValor: R${preco_produto:.2f}\n"
        f"Só responder com a forma de pagamento pra confirmar. Se não quiser, pode ignorar, prometo não ficar (muito) chateado! 😅"
        f"\n\n(Foto: {foto_produto})"
    )

    print("-"*60)
    print(">> Mensagem gerada para:", nome)
    print(mensagem)
    print("-"*60)
