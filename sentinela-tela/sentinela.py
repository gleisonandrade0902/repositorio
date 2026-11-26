"""
Sentinela de Tela — mantém a tela ligada só enquanto o DONO olha para ela.

Regras:
  • Dono olhando              -> tela fica ligada (impede descanso de tela)
  • Ninguém por N segundos    -> desliga a tela
  • Dono volta                -> liga a tela
  • Outra pessoa (sem o dono) -> bloqueia o computador
  • Ausente por X minutos     -> bloqueia o computador

Uso:
  python sentinela.py cadastrar      # grava a assinatura facial do dono
  python sentinela.py                # roda o monitoramento
  python sentinela.py --preview      # roda mostrando a câmera (diagnóstico)
"""
import argparse
import gc
import json
import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

import sistema
from visao import Visao

BASE = Path(__file__).parent
ARQ_CONFIG = BASE / "config.json"
ARQ_DONO = BASE / "dono.npy"

PADRAO = {
    "camera_indice": 0,
    "fps_verificacao": 3,              # análises por segundo
    "largura_processamento": 320,      # px; menor = menos RAM/CPU
    "limiar_reconhecimento": 0.40,     # cosseno SFace (0.363 = padrão OpenCV)
    "exigir_olhar_para_tela": True,
    "yaw_max": 0.35,                   # tolerância de cabeça virada
    "segundos_para_desligar_tela": 8,
    "minutos_para_bloquear": 5,
    "bloquear_se_estranho": True,
    "verificacoes_para_estranho": 4,   # confirmações seguidas antes de bloquear
    "bloquear_estranho_mesmo_com_dono": False,  # anti "espiada por cima do ombro"
    "limite_memoria_mb": 300,
    "amostras_cadastro": 25,
}

log = logging.getLogger("sentinela")


def carregar_config():
    cfg = dict(PADRAO)
    if ARQ_CONFIG.exists():
        cfg.update(json.loads(ARQ_CONFIG.read_text(encoding="utf-8")))
    else:
        ARQ_CONFIG.write_text(json.dumps(PADRAO, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def abrir_camera(indice):
    api = cv2.CAP_DSHOW if sistema.SO == "Windows" else cv2.CAP_ANY
    cam = cv2.VideoCapture(indice, api)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # sempre o frame mais recente
    if not cam.isOpened():
        raise RuntimeError(f"Não foi possível abrir a câmera {indice}")
    return cam


# --------------------------------------------------------------------------
# Guarda de memória: se passar do limite, reduz a qualidade em degraus.
# --------------------------------------------------------------------------
class GuardaMemoria:
    DEGRAUS = [  # (largura_processamento, fps)
        (320, 3), (256, 2), (192, 2), (160, 1),
    ]

    def __init__(self, limite_mb):
        self.limite = limite_mb
        self.nivel = 0
        try:
            import psutil
            self._proc = psutil.Process()
        except ImportError:
            self._proc = None
            log.warning("psutil não instalado: monitor de memória desativado")

    def uso_mb(self):
        return self._proc.memory_info().rss / 1048576 if self._proc else 0.0

    def checar(self, visao, cfg):
        uso = self.uso_mb()
        if uso > self.limite:
            gc.collect()
            uso = self.uso_mb()
        if uso > self.limite and self.nivel < len(self.DEGRAUS) - 1:
            self.nivel += 1
            larg, fps = self.DEGRAUS[self.nivel]
            visao.largura, cfg["fps_verificacao"] = larg, fps
            log.warning("Memória %.0f MB > %d MB: modo econômico %d (%dpx, %d fps)",
                        uso, self.limite, self.nivel, larg, fps)
        elif uso > self.limite:
            log.error("Memória %.0f MB ainda acima do limite no modo mais econômico", uso)
        return uso


# --------------------------------------------------------------------------
def cadastrar(cfg):
    visao = Visao(cfg["largura_processamento"])
    cam = abrir_camera(cfg["camera_indice"])
    alvo = cfg["amostras_cadastro"]
    amostras = []
    print(f"Olhe para a câmera e mova levemente a cabeça. Coletando {alvo} amostras...")
    try:
        while len(amostras) < alvo:
            ok, frame = cam.read()
            if not ok:
                continue
            pequeno, escala, faces = visao.detectar(frame)
            if len(faces) == 1:
                amostras.append(visao.assinatura(pequeno, faces[0]))
                print(f"  amostra {len(amostras)}/{alvo}", end="\r")
                time.sleep(0.25)  # variedade entre amostras
            elif len(faces) > 1:
                print("  Mais de um rosto na imagem — fique sozinho(a).   ", end="\r")
    finally:
        cam.release()
    np.save(ARQ_DONO, np.array(amostras, np.float32))
    print(f"\nCadastro salvo em {ARQ_DONO.name} (só números, nenhuma foto é guardada).")


# --------------------------------------------------------------------------
class Sentinela:
    def __init__(self, cfg, preview=False):
        if not ARQ_DONO.exists():
            sys.exit("Nenhum dono cadastrado. Rode: python sentinela.py cadastrar")
        self.cfg = cfg
        self.preview = preview
        self.visao = Visao(cfg["largura_processamento"], 0.8,
                           cfg["limiar_reconhecimento"], cfg["yaw_max"])
        self.visao.carregar_dono(ARQ_DONO)
        self.memoria = GuardaMemoria(cfg["limite_memoria_mb"])
        self.resetar()

    def resetar(self):
        agora = time.time()
        self.ultimo_dono = agora
        self.tela_ligada = True
        self.cont_estranho = 0

    # ---- ações ----------------------------------------------------------
    def _desligar(self):
        if self.tela_ligada:
            log.info("Ninguém olhando: desligando tela")
            sistema.manter_tela_ligada(False)
            sistema.desligar_tela()
            self.tela_ligada = False

    def _ligar(self):
        if not self.tela_ligada:
            log.info("Dono voltou: ligando tela")
            sistema.ligar_tela()
            self.tela_ligada = True

    def _bloquear(self, motivo, cam):
        log.warning("BLOQUEANDO: %s", motivo)
        sistema.manter_tela_ligada(False)
        sistema.bloquear()
        cam.release()  # libera a câmera (LED apaga) enquanto bloqueado
        time.sleep(3)
        while sistema.sessao_bloqueada():
            time.sleep(2)
        log.info("Sessão desbloqueada: retomando monitoramento")
        self.resetar()
        return abrir_camera(self.cfg["camera_indice"])

    # ---- decisão --------------------------------------------------------
    def decidir(self, rostos, agora):
        """Retorna 'bloquear:<motivo>' | 'ligar' | 'desligar' | None."""
        c = self.cfg
        dono = any(r.eh_dono and (r.olhando or not c["exigir_olhar_para_tela"]) for r in rostos)
        dono_visivel = any(r.eh_dono for r in rostos)
        estranhos = [r for r in rostos if not r.eh_dono]

        if c["bloquear_se_estranho"] and estranhos and (
                not dono_visivel or c["bloquear_estranho_mesmo_com_dono"]):
            self.cont_estranho += 1
            if self.cont_estranho >= c["verificacoes_para_estranho"]:
                return "bloquear:outra pessoa diante da tela"
        else:
            self.cont_estranho = 0

        if dono:
            self.ultimo_dono = agora
            return "ligar"

        ausente = agora - self.ultimo_dono
        if ausente >= c["minutos_para_bloquear"] * 60:
            return "bloquear:ausência prolongada"
        if ausente >= c["segundos_para_desligar_tela"]:
            return "desligar"
        return None

    # ---- laço principal -------------------------------------------------
    def rodar(self):
        cam = abrir_camera(self.cfg["camera_indice"])
        log.info("Sentinela ativa. Ctrl+C para sair.")
        prox_check_mem = 0
        try:
            while True:
                inicio = time.time()
                ok, frame = cam.read()
                if not ok:
                    log.error("Falha na leitura da câmera; tentando reabrir")
                    cam.release()
                    time.sleep(2)
                    cam = abrir_camera(self.cfg["camera_indice"])
                    continue

                rostos = self.visao.analisar(frame)
                acao = self.decidir(rostos, inicio)

                if acao == "ligar":
                    self._ligar()
                    sistema.manter_tela_ligada(True)
                elif acao == "desligar":
                    self._desligar()
                elif acao and acao.startswith("bloquear:"):
                    cam = self._bloquear(acao.split(":", 1)[1], cam)

                if self.preview:
                    self._desenhar(frame, rostos)

                if inicio >= prox_check_mem:
                    uso = self.memoria.checar(self.visao, self.cfg)
                    log.debug("RAM: %.0f MB", uso)
                    prox_check_mem = inicio + 10

                espera = 1.0 / self.cfg["fps_verificacao"] - (time.time() - inicio)
                if espera > 0:
                    time.sleep(espera)
        except KeyboardInterrupt:
            log.info("Encerrado pelo usuário")
        finally:
            sistema.manter_tela_ligada(False)
            if not self.tela_ligada:
                sistema.ligar_tela()
            cam.release()
            if self.preview:
                cv2.destroyAllWindows()

    @staticmethod
    def _desenhar(frame, rostos):
        for r in rostos:
            x, y, w, h = r.caixa
            cor = (0, 200, 0) if r.eh_dono else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)
            txt = f"{'DONO' if r.eh_dono else 'OUTRO'} {r.similaridade:.2f}"
            txt += "" if r.olhando else " (virado)"
            cv2.putText(frame, txt, (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 1)
        cv2.imshow("Sentinela (preview)", frame)
        cv2.waitKey(1)


def main():
    ap = argparse.ArgumentParser(description="Sentinela de Tela")
    ap.add_argument("comando", nargs="?", default="rodar", choices=["rodar", "cadastrar"])
    ap.add_argument("--preview", action="store_true", help="mostra a câmera com marcações")
    ap.add_argument("--debug", action="store_true", help="log detalhado (inclui uso de RAM)")
    a = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if a.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(BASE / "sentinela.log", encoding="utf-8")])
    cfg = carregar_config()
    if a.comando == "cadastrar":
        cadastrar(cfg)
    else:
        Sentinela(cfg, a.preview).rodar()


if __name__ == "__main__":
    main()
