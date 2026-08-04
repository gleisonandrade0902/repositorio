#!/usr/bin/env bash
# Gera um executável standalone (Linux/macOS) do Gerador de Diário Oficial.
set -e
cd "$(dirname "$0")"

python3 -m venv .venv_build
source .venv_build/bin/activate
pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --windowed \
    --name "GeradorDiarioOficial" \
    --add-data "config.json:." \
    --add-data "ativos:ativos" \
    gerar_diario.py

deactivate
echo
echo "Executável gerado em: dist/GeradorDiarioOficial"
