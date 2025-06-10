@echo off
REM Ativa ambiente virtual e instala dependências

REM Cria ambiente virtual se não existir
if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
)

echo Ativando ambiente virtual...
call venv\Scripts\activate

echo Instalando dependências...
pip install -r requirements.txt

echo Ambiente pronto. Você pode agora rodar:
echo     python main.py
pause