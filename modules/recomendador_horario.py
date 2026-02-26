# modules/ml_horario_personalizado.py

from datetime import datetime, timedelta
import os
import pandas as pd
import urllib.parse
from core.database import executar_consulta
from utils.formatters import validar_numero, formatar_nome
from utils.sent_status import ja_enviado, marcar_como_enviado, registrar_log
from utils.message_queue import adicionar_na_fila

# Carregar possíveis preços customizados
def carregar_precos_customizados(caminho="config/precos_custom.json"):
    if os.path.exists(caminho):
        import json
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def should_run():
#    # Roda toda hora cheia, exceto segunda-feira
    agora = datetime.now()
    horario = agora.time()
    dentro_do_horario = (horario >= datetime.strptime("17:30", "%H:%M").time() and
                         horario <= datetime.strptime("22:30", "%H:%M").time())
    return (
        agora.weekday() != 0             # Não executa na segunda-feira
        and agora.minute == 22           # Só em hora cheia
        and dentro_do_horario            # Só entre 17:30 e 22:30
    )


# Teste para rodar a cada minuto
#ultima_execucao = datetime.min
#intervalo_execucao = timedelta(seconds=25)
#def should_run():
#    global ultima_execucao
#    agora = datetime.now()
#    if agora - ultima_execucao >= intervalo_execucao:
#        ultima_execucao = agora
#        return True
#    return False



def run(driver):
    sql = """
        SELECT 
            i.CODIGOPEDIDO,
            p.DATAABERTURA,
            i.NOMEPRODUTO,
            pt.nome AS NOME_PRODUTO,
            pd.CODIGOPRODUTO,
            pd.PRECOVENDA,
            i.QUANTIDADE,
            p.CODIGOCONTATOCLIENTE,
            c.NOME,
            c.FONEPRINCIPAL,
            c.ENDERECO,
            c.NUMERO,
            c.BAIRRO
        FROM 
            ITENSPEDIDO i 
        INNER JOIN 
            PEDIDOS p ON i.CODIGOPEDIDO = p.CODIGO
        INNER JOIN
            ITEMPEDIDOTIPO t ON i.CODIGOITEMPEDIDOTIPO = t.CODIGO
        INNER JOIN
            PRODUTODETALHE pd ON i.CODIGOPRODUTODETALHE = pd.CODIGO
        INNER JOIN
            PRODUTOS pt ON pd.CODIGOPRODUTO = pt.CODIGO
        INNER JOIN
            CONTATOS c ON p.CODIGOCONTATOCLIENTE = c.CODIGO
        WHERE 
            p.DATADELETE IS NULL AND t.CODIGO NOT IN (1,2) AND pd.CODIGOPRODUTOTAMANHO NOT IN (2) AND t.CODIGO != 6
        ORDER BY 
            p.DATAABERTURA DESC;
    """
    resultados = executar_consulta(sql)

    # Construção do DataFrame
    colunas = [
        "codigopedido", "dataabertura", "nomeproduto", "nome_produto", "codigoproduto", "precovenda", "quantidade",
        "codigocontatocliente", "nome", "foneprincipal", "endereco", "numero", "bairro"
    ]
    
    df = pd.DataFrame(resultados, columns=colunas)
    if df.empty:
        return

    # Pré-processamento
    df["dataabertura"] = pd.to_datetime(df["dataabertura"])
    df = df[df["foneprincipal"].notnull() & (df["foneprincipal"] != '')]
    df = df[df["nome"].notnull() & (df["nome"] != '')]


    # Extração: hora/dia do pedido
    df["hora"] = df["dataabertura"].dt.hour
    df["dia_semana"] = df["dataabertura"].dt.weekday
 

    # Identifica para cada cliente:
    clientes = []
    for cliente_id, grupo in df.groupby("codigocontatocliente"):
        # Conta pedidos por hora/dia da semana
        grupo_horario = grupo.groupby(["dia_semana", "hora"]).size()
        if grupo_horario.empty:
            continue
        dia_mais_frequente, hora_mais_frequente = grupo_horario.idxmax()


        # Produto mais comprado pelo cliente
        produto_top = grupo.groupby("codigoproduto")["quantidade"].sum().idxmax()
        prod_row = grupo[grupo["codigoproduto"] == produto_top].iloc[0]


        # Último pedido
        dt_ultimo = grupo["dataabertura"].max()

        clientes.append({
            "codigocontatocliente": cliente_id,
            "nome": prod_row["nome"],  # Usa nome do cliente
            "fone": prod_row["foneprincipal"],
            "endereco": prod_row["endereco"],
            "numero": prod_row["numero"],
            "bairro": prod_row["bairro"],
            "dia_semana_fav": dia_mais_frequente,
            "hora_fav": hora_mais_frequente,
            "produto_nome": prod_row["nome_produto"],
            "codigoproduto": prod_row["codigoproduto"],
            "preco": prod_row["precovenda"],
            "qtde_pedidos": len(grupo["codigopedido"].unique()),
            "data_ultimo_pedido": dt_ultimo,
        })

    # DataFrame final
    df_clientes = pd.DataFrame(clientes)
    if df_clientes.empty:
        return

    # Só clientes há mais de 15 dias sem pedir
    limite_data = datetime.now() - timedelta(days=15)
    df_clientes = df_clientes[df_clientes["data_ultimo_pedido"] < limite_data]

    # Determina próximo horário de disparo
    agora = datetime.now()
    prox_hora = agora.hour if agora.hour < 23 else 0
    dia_semana = agora.weekday()

    # Filtra para quem normalmente pede nesse horário/dia
    df_filtro = df_clientes[
        (df_clientes["dia_semana_fav"] == dia_semana) &
        (df_clientes["hora_fav"] == prox_hora)
    ]

    # Ordena por qtde de pedidos (maior primeiro), pega 7
    df_top7 = df_filtro.sort_values("qtde_pedidos", ascending=False).head(7)

    # Carrega preços customizados (se houver)
    precos_custom = carregar_precos_customizados()

    print("\n=== DEBUG: Lista dos 7 clientes e seus horários preferidos ===")
    for idx, row in df_top7.iterrows():
        print(f"Cliente: {row['nome']} | Tel: {row['fone']} | Dia da Semana: {row['dia_semana_fav']} | Hora: {row['hora_fav']}")
        print("==============================================================\n")
        nome = formatar_nome(row["nome"])
        numero = validar_numero(row["fone"])
        if not numero or not nome:
            continue


        # Usa preço customizado apenas de terça a quinta
        dia_semana_hoje = datetime.now().weekday()
        if dia_semana_hoje in [1, 2, 3]:  # terça, quarta, quinta
            preco = precos_custom.get(str(row["codigoproduto"]), row["preco"])
        else:
            preco = row["preco"]

        endereco = row["endereco"] or ""
        numero_end = row["numero"] or ""
        bairro = row["bairro"] or ""
        texto_endereco = ""
        if endereco and numero_end and bairro:
            texto_endereco = f"\n*Endereço de entrega:* {endereco}, {numero_end} - {bairro}"

        caminho_foto = os.path.abspath(f"videos/imagens_pizza/{row['codigoproduto']}.jpg")
        nome_produto = row["produto_nome"]

        mensagem_texto = (
            f"{nome}, aqui é o Teddy🐻 da pizzaria! 🍕\n"
            f"Como eu sou um urso bem informado, sei que você *AMA* pedir uma *PIZZA {nome_produto}* "
            f"neste horário. 😉\n\n"
            f"O que acha de repetir o pedido hoje? O valor está *R${preco:.2f}*.\n{texto_endereco}\n"
            f"Confirma que já mando preparar. Se não, vou comer sozinho mesmo!"
        )

        mensagem = urllib.parse.quote(mensagem_texto)

        adicionar_na_fila({
            "numero": numero,
            "nome": nome,
            "mensagem": mensagem,
            "caminho_video": caminho_foto,
            "log": f"ML - Mensagem personalizada enviada para cliente com padrão de horário"
        })

        marcar_como_enviado(f"ML_PERS-{numero}-{row['codigoproduto']}-{prox_hora}-{dia_semana}")
        registrar_log(numero, nome, "Mensagem personalizada por ML enviada")

# Exemplo de arquivo JSON para preços customizados:
# config/precos_custom.json
# {
#   "1005": 52.00,
#   "1010": 48.90,
#   "1055": 57.50
# }