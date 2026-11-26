"""
Sentinela de Tela — Modo Pro (painel gráfico + ícone na bandeja).

  pythonw app.py               abre o painel
  pythonw app.py --minimizado  inicia direto na bandeja (usado na inicialização)
"""
import argparse
import logging
import os
import socket
import sys
import threading
from logging.handlers import RotatingFileHandler

import config
from banco import Banco, SISTEMA
from config import PASTA_DADOS

PORTA_INSTANCIA = 47863  # só em 127.0.0.1: garante uma única instância


def instancia_unica(fila_ui_getter):
    """Se já houver um Sentinela aberto, pede para ele se mostrar e sai."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", PORTA_INSTANCIA))
    except OSError:
        try:
            with socket.create_connection(("127.0.0.1", PORTA_INSTANCIA), timeout=2) as c:
                c.sendall(b"mostrar")
        except OSError:
            pass
        sys.exit(0)
    srv.listen(1)

    def ouvir():
        while True:
            con, _ = srv.accept()
            with con:
                if con.recv(16) == b"mostrar":
                    fila = fila_ui_getter()
                    if fila:
                        fila.put("mostrar")

    threading.Thread(target=ouvir, daemon=True).start()


def main():
    ap = argparse.ArgumentParser(description="Sentinela de Tela — Modo Pro")
    ap.add_argument("--minimizado", action="store_true")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    PASTA_DADOS.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if a.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%d/%m %H:%M:%S",
        handlers=[RotatingFileHandler(PASTA_DADOS / "sentinela.log", maxBytes=1_000_000,
                                      backupCount=3, encoding="utf-8")]
        + ([logging.StreamHandler()] if sys.stdout else []))

    ref = {}
    instancia_unica(lambda: ref.get("fila"))

    from interface import App  # importa Tk só depois de garantir instância única
    from nucleo import Motor, migrar_v1

    cfg = config.carregar()
    banco = Banco()
    migrar_v1(banco)
    motor = Motor(cfg, banco)
    banco.registrar(SISTEMA, "Sentinela iniciado", visto=True)
    motor.start()

    try:
        app = App(cfg, banco, motor, minimizado=a.minimizado)
        ref["fila"] = app.fila_ui
        if not banco.listar_pessoas():
            app.after(600, lambda: (app.mostrar(), app.abas.select(app.aba_pessoas),
                                    app.aba_pessoas.adicionar()))
        app.mainloop()
    except Exception:
        logging.exception("Falha na interface")
    finally:
        motor.parar()
        motor.join(timeout=5)
        banco.registrar(SISTEMA, "Sentinela encerrado", visto=True)
        logging.shutdown()
        os._exit(0)  # encerra também a thread do ícone da bandeja


if __name__ == "__main__":
    main()
