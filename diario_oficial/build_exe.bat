@echo off
REM Gera um executavel standalone (Windows) do Gerador de Diario Oficial.
cd /d "%~dp0"

python -m venv .venv_build
call .venv_build\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --windowed ^
    --name "GeradorDiarioOficial" ^
    --add-data "config.json;." ^
    --add-data "ativos;ativos" ^
    gerar_diario.py

call .venv_build\Scripts\deactivate.bat
echo.
echo Executavel gerado em: dist\GeradorDiarioOficial.exe
pause
