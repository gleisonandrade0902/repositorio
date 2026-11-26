@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Preparando o Sentinela pela primeira vez...
  python -m venv .venv || (echo Instale o Python 3.10+ marcando "Add to PATH". & pause & exit /b 1)
  .venv\Scripts\pip install -r requirements.txt
)
if not exist modelos\face_recognition_sface_2021dec.onnx .venv\Scripts\python baixar_modelos.py
rem pythonw = sem janela de console
start "" .venv\Scripts\pythonw app.py
