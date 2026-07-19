#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Criando ambiente virtual..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --quiet -r requirements.txt

echo "======================================================"
echo "  GeSUAS Local rodando em: http://127.0.0.1:${PORT:-5000}"
echo "  Pressione Ctrl+C para encerrar."
echo "======================================================"
python app.py
