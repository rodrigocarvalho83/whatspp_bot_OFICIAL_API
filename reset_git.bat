@echo off
set "SRC=whatsapp-bot"
set "DST=whatsapp-bot-limpo"

echo 🔄 Criando novo diretório: %DST%
mkdir %DST%

echo 📁 Copiando arquivos de %SRC% para %DST% (exceto .git)...
robocopy %SRC% %DST% /E /XD ".git" "__pycache__" /XF ".DS_Store"

cd %DST%

echo 🧹 Removendo qualquer .git restante...
rmdir /S /Q .git 2>nul

echo 🔃 Inicializando novo repositório Git...
git init
git add .
git commit -m "Reinicialização do projeto sem histórico corrompido"

echo ✅ Repositório limpo criado em %DST%
echo (Opcional: configure o remoto com 'git remote add origin <url>' e envie com 'git push -u origin main --force')
pause
