"""
Sentinela de Tela — modo linha de comando (sem interface gráfica).

  python sentinela.py cadastrar --nome "Maria"   cadastra uma pessoa
  python sentinela.py                            monitora (Ctrl+C para sair)

Para o painel gráfico completo (Modo Pro), use: python app.py
"""
import argparse
import logging
import time

import config
from banco import Banco
from nucleo import Coletor, Motor, abrir_camera, migrar_v1


def cadastrar(cfg, banco, motor, nome):
    cam = abrir_camera(cfg["camera_indice"])
    col = Coletor(motor.visao, cfg["amostras_cadastro"])
    print(f"Cadastrando {nome}: olhe para a câmera e mova levemente a cabeça…")
    try:
        while not col.concluido:
            ok, frame = cam.read()
            if ok:
                msg, *_ = col.processar(frame)
                print(f"  {msg} {len(col.amostras)}/{col.alvo}        ", end="\r")
    finally:
        cam.release()
    banco.adicionar_pessoa(nome, col.resultado())
    print(f"\n{nome} cadastrado(a). Nenhuma foto foi guardada.")


def main():
    ap = argparse.ArgumentParser(description="Sentinela de Tela (CLI)")
    ap.add_argument("comando", nargs="?", default="rodar", choices=["rodar", "cadastrar"])
    ap.add_argument("--nome", default="Dono")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.debug else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    cfg = config.carregar()
    banco = Banco()
    migrar_v1(banco)
    motor = Motor(cfg, banco)
    if a.comando == "cadastrar":
        return cadastrar(cfg, banco, motor, a.nome)
    if not banco.listar_pessoas():
        raise SystemExit('Ninguém cadastrado. Rode: python sentinela.py cadastrar --nome "Seu nome"')
    motor.start()
    try:
        while motor.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        motor.parar()
        motor.join(5)


if __name__ == "__main__":
    main()
