@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
  .venv\Scripts\python baixar_modelos.py
)
if not exist dono.npy .venv\Scripts\python sentinela.py cadastrar
rem pythonw = sem janela de console. Troque por python para ver o log ao vivo.
start "" .venv\Scripts\pythonw sentinela.py
