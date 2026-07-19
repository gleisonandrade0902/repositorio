@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Criando ambiente virtual...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install --quiet -r requirements.txt

echo ======================================================
echo   GeSUAS Local rodando em: http://127.0.0.1:5000
echo   Feche esta janela para encerrar.
echo ======================================================
python app.py
pause
