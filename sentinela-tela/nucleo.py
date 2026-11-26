"""
Motor do Sentinela: roda numa thread e toma todas as decisões.

Modos:
  • PC desbloqueado  -> mantém/desliga/liga tela; bloqueia se estranho/ausência
  • PC bloqueado     -> (se habilitado) vigia a tela de bloqueio: fotografa
                        estranhos e quem digitar senha incorreta (evento 4625)
  • Pausado / câmera emprestada ao cadastro

A interface conversa com o motor por métodos thread-safe e pela fila
`motor.eventos` (o motor nunca toca em widgets Tk).
"""
import gc
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import banco as bd
import sistema
from config import ARQ_FALHAS_LOGIN, BASE, PASTA_CAPTURAS
from visao import Visao, desenhar

log = logging.getLogger("sentinela.nucleo")


def abrir_camera(indice):
    api = cv2.CAP_DSHOW if sistema.SO == "Windows" else cv2.CAP_ANY
    cam = cv2.VideoCapture(indice, api)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # sempre o frame mais recente
    if not cam.isOpened():
        cam.release()
        raise RuntimeError(f"Não foi possível abrir a câmera {indice}")
    return cam


def migrar_v1(banco):
    """Importa o dono.npy da versão 1 como pessoa 'Dono'."""
    antigo = BASE / "dono.npy"
    if antigo.exists() and not banco.listar_pessoas():
        banco.adicionar_pessoa("Dono", np.load(antigo))
        antigo.rename(antigo.with_suffix(".npy.migrado"))
        log.info("Cadastro da versão 1 importado como 'Dono'")


# --------------------------------------------------------------------------
class Coletor:
    """Coleta amostras para cadastro, frame a frame (usado pela GUI e pela CLI)."""

    def __init__(self, visao, alvo):
        self.visao, self.alvo = visao, alvo
        self.amostras = []
        self._ultimo = 0.0

    @property
    def progresso(self):
        return len(self.amostras) / self.alvo

    @property
    def concluido(self):
        return len(self.amostras) >= self.alvo

    def processar(self, frame):
        """Retorna (mensagem, faces) e acumula amostra quando houver 1 rosto."""
        pequeno, escala, faces = self.visao.detectar(frame)
        if len(faces) == 0:
            return "Nenhum rosto — olhe para a câmera", faces, escala
        if len(faces) > 1:
            return "Mais de um rosto — fique sozinho(a) na imagem", faces, escala
        if time.time() - self._ultimo >= 0.25:  # variedade entre amostras
            self.amostras.append(self.visao.assinatura(pequeno, faces[0]))
            self._ultimo = time.time()
        return "Ótimo! Mova levemente a cabeça…", faces, escala

    def resultado(self):
        return np.array(self.amostras, np.float32)


# --------------------------------------------------------------------------
class GuardaMemoria:
    """Se passar do limite, reduz a qualidade em degraus."""
    DEGRAUS = [(320, 3), (256, 2), (192, 2), (160, 1)]  # (largura, fps)

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
        return uso


# --------------------------------------------------------------------------
class Motor(threading.Thread):
    def __init__(self, cfg, banco):
        super().__init__(daemon=True, name="motor")
        self.cfg, self.banco = cfg, banco
        self.visao = Visao(cfg["largura_processamento"], 0.8,
                           cfg["limiar_reconhecimento"], cfg["yaw_max"])
        self.memoria = GuardaMemoria(cfg["limite_memoria_mb"])
        self.eventos = queue.Queue()          # -> interface
        self._parar = threading.Event()
        self._pedido_cam = threading.Event()  # cadastro pediu a câmera
        self._cam_livre = threading.Event()
        self._bloquear_ja = threading.Event()
        self.pausado = False
        self.preview_ativo = False
        self.frame_preview = None             # ndarray BGR pequeno (só se preview_ativo)
        self.status = {"modo": "iniciando", "presentes": [], "ram": 0.0,
                       "tela_ligada": True, "economia": 0, "erro": ""}
        self.cam = None
        self._resetar()
        self._em_bloqueio = False
        self._id_antes_bloqueio = 0
        self._ultima_captura_bloq = 0.0
        self._falhas_base = sistema.contar_falhas_login(ARQ_FALHAS_LOGIN)
        self._prox_limpeza = 0.0
        self._prox_mem = 0.0
        self._prox_check_bloq = 0.0
        self._bloqueada_cache = False
        self._carencia_ate = 0.0
        self.recarregar_pessoas()

    # ======== API para a interface (thread-safe) ==========================
    def recarregar_pessoas(self):
        self.visao.carregar_pessoas(self.banco.assinaturas_ativas())

    def aplicar_config(self):
        self.visao.limiar_rec = self.cfg["limiar_reconhecimento"]
        self.visao.yaw_max = self.cfg["yaw_max"]
        self.memoria.limite = self.cfg["limite_memoria_mb"]
        if self.memoria.nivel == 0:
            self.visao.largura = self.cfg["largura_processamento"]
        if self.cam is not None:
            self._liberar_camera()  # reabre (índice pode ter mudado)

    def pausar(self, sim=True):
        self.pausado = sim
        if sim:
            sistema.manter_tela_ligada(False)
        self._emitir("status")

    def bloquear_agora(self):
        self._bloquear_ja.set()

    def emprestar_camera(self, timeout=5.0):
        """Libera a câmera para o cadastro. Retorna True quando livre."""
        self._cam_livre.clear()
        self._pedido_cam.set()
        return self._cam_livre.wait(timeout)

    def devolver_camera(self):
        self._pedido_cam.clear()

    def parar(self):
        self._parar.set()

    @property
    def falha_senha_configurada(self):
        return self._falhas_base >= 0

    # ======== internos =====================================================
    def _emitir(self, tipo, dado=None):
        self.eventos.put((tipo, dado))

    def _resetar(self):
        self.ultimo_autorizado = time.time()
        self.tela_ligada = True
        self.cont_estranho = 0

    def _liberar_camera(self):
        if self.cam is not None:
            self.cam.release()
            self.cam = None

    def _ler_frame(self):
        if self.cam is None:
            self.cam = abrir_camera(self.cfg["camera_indice"])
            self.status["erro"] = ""
        ok, frame = self.cam.read()
        if not ok:
            self._liberar_camera()
            raise RuntimeError("Falha na leitura da câmera")
        return frame

    def _sessao_bloqueada(self, agora):
        if agora >= self._prox_check_bloq:  # no Linux é um subprocesso: 1x/s basta
            self._bloqueada_cache = sistema.sessao_bloqueada()
            self._prox_check_bloq = agora + 1.0
        return self._bloqueada_cache

    def _capturar(self, frame, rostos, tipo, descricao, visto=False):
        foto = None
        if self.cfg["capturar_fotos"] and frame is not None:
            img = desenhar(frame.copy(), rostos)
            carimbo = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            cv2.rectangle(img, (0, img.shape[0] - 26), (img.shape[1], img.shape[0]), (0, 0, 0), -1)
            cv2.putText(img, f"Sentinela de Tela - {carimbo} - {bd.ROTULOS[tipo]}",
                        (8, img.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        (255, 255, 255), 1, cv2.LINE_AA)
            foto = PASTA_CAPTURAS / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{tipo}.jpg"
            cv2.imwrite(str(foto), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        sim = max((r.similaridade for r in rostos), default=None)
        eid = self.banco.registrar(tipo, descricao, foto, sim, visto)
        log.warning("%s: %s", bd.ROTULOS[tipo], descricao)
        self._emitir("novo_evento", eid)
        return eid

    def _inicio_bloqueio(self):
        self._em_bloqueio = True
        self._id_antes_bloqueio = self.banco.ultimo_id()
        # Zera a referência: falhas ocorridas com o PC em uso (ex.: UAC) não contam
        self._falhas_base = sistema.contar_falhas_login(ARQ_FALHAS_LOGIN)
        self._emitir("bloqueio")

    def _bloquear(self, motivo, frame=None, rostos=(), intruso=False):
        self._inicio_bloqueio()
        if intruso:
            self._capturar(frame, list(rostos), bd.INTRUSO_SESSAO, motivo)
        else:
            self.banco.registrar(bd.BLOQUEIO, motivo, visto=True)
        sistema.manter_tela_ligada(False)
        sistema.bloquear()
        self._carencia_ate = time.time() + 4  # o SO leva um instante para bloquear
        self._bloqueada_cache = True
        self._prox_check_bloq = time.time() + 4

    # ---- regras com o PC desbloqueado -----------------------------------
    def decidir(self, rostos, agora):
        """Retorna 'bloquear:<motivo>' | 'ligar' | 'desligar' | None."""
        c = self.cfg
        presente = any(r.autorizado and (r.olhando or not c["exigir_olhar_para_tela"])
                       for r in rostos)
        autorizado_visivel = any(r.autorizado for r in rostos)
        estranhos = [r for r in rostos if not r.autorizado]

        if c["bloquear_se_estranho"] and estranhos and (
                not autorizado_visivel or c["bloquear_estranho_mesmo_com_dono"]):
            self.cont_estranho += 1
            if self.cont_estranho >= c["verificacoes_para_estranho"]:
                self.cont_estranho = 0
                return "bloquear:Pessoa não cadastrada diante do computador"
        else:
            self.cont_estranho = 0

        if presente:
            self.ultimo_autorizado = agora
            return "ligar"
        ausente = agora - self.ultimo_autorizado
        if ausente >= c["minutos_para_bloquear"] * 60:
            return "bloquear:Ausência prolongada"
        if ausente >= c["segundos_para_desligar_tela"]:
            return "desligar"
        return None

    def _ciclo_desbloqueado(self, agora):
        if self._em_bloqueio:  # acabou de desbloquear
            self._em_bloqueio = False
            self._resetar()
            log.info("Sessão desbloqueada")
            novas = self.banco.nao_vistas(self._id_antes_bloqueio)
            if novas and self.cfg["alerta_ao_desbloquear"]:
                self._emitir("alerta", [dict(r) for r in novas])

        frame = self._ler_frame()
        rostos = self.visao.analisar(frame)
        self.status["modo"] = "monitorando"
        self.status["presentes"] = [r.nome or "desconhecido" for r in rostos]

        if self._bloquear_ja.is_set():
            self._bloquear_ja.clear()
            self._bloquear("Bloqueio manual pelo painel")
            return frame, rostos

        if self.visao.total_pessoas == 0:  # sem ninguém cadastrado, só observa
            self.status["modo"] = "sem pessoas cadastradas"
            return frame, rostos

        acao = self.decidir(rostos, agora)
        if acao == "ligar":
            if not self.tela_ligada:
                log.info("Pessoa autorizada voltou: ligando tela")
                sistema.ligar_tela()
                self.tela_ligada = True
            sistema.manter_tela_ligada(True)
        elif acao == "desligar" and self.tela_ligada:
            log.info("Ninguém olhando: desligando tela")
            sistema.manter_tela_ligada(False)
            sistema.desligar_tela()
            self.tela_ligada = False
        elif acao and acao.startswith("bloquear:"):
            motivo = acao.split(":", 1)[1]
            self._bloquear(motivo, frame, rostos, intruso=motivo.startswith("Pessoa"))
        self.status["tela_ligada"] = self.tela_ligada
        return frame, rostos

    # ---- vigilância da tela de bloqueio ---------------------------------
    def _ciclo_bloqueado(self, agora):
        if not self._em_bloqueio:  # bloqueado por fora (Win+L, tampa etc.)
            self._inicio_bloqueio()
        if not self.cfg["vigiar_durante_bloqueio"]:
            self._liberar_camera()  # LED apaga
            self.status.update(modo="bloqueado", presentes=[])
            return None, []

        self.status["modo"] = "vigiando tela de bloqueio"
        frame = self._ler_frame()
        rostos = self.visao.analisar(frame)
        self.status["presentes"] = [r.nome or "desconhecido" for r in rostos]
        autorizados = [r for r in rostos if r.autorizado]

        # 1) Senha incorreta (registrada pelo Windows) -> foto imediata
        falhas = sistema.contar_falhas_login(ARQ_FALHAS_LOGIN)
        if falhas > self._falhas_base >= 0:
            n = falhas - self._falhas_base
            if autorizados:  # a própria pessoa errou a senha: registra sem foto
                self.banco.registrar(bd.SENHA_INCORRETA,
                                     f"{n} senha(s) incorreta(s) por {autorizados[0].nome}", visto=True)
            else:
                quem = "rosto não cadastrado" if rostos else "nenhum rosto visível na câmera"
                self._capturar(frame, rostos, bd.SENHA_INCORRETA,
                               f"{n} senha(s) incorreta(s) — {quem}")
                self._ultima_captura_bloq = agora
        if falhas >= 0:
            self._falhas_base = falhas

        # 2) Estranho parado diante da tela de bloqueio
        if rostos and not autorizados:
            self.cont_estranho += 1
            if (self.cont_estranho >= self.cfg["verificacoes_para_estranho"]
                    and agora - self._ultima_captura_bloq >= self.cfg["intervalo_entre_capturas_s"]):
                self._capturar(frame, rostos, bd.INTRUSO_BLOQUEIO,
                               f"{len(rostos)} pessoa(s) não cadastrada(s) diante da tela de bloqueio")
                self._ultima_captura_bloq = agora
                self.cont_estranho = 0
        else:
            self.cont_estranho = 0
        return frame, rostos

    # ---- laço principal --------------------------------------------------
    def run(self):
        log.info("Motor iniciado (%d pessoa(s) cadastrada(s))", self.visao.total_pessoas)
        while not self._parar.is_set():
            inicio = time.time()
            fps = self.cfg["fps_verificacao"]
            try:
                if self._pedido_cam.is_set():
                    self._liberar_camera()
                    self._cam_livre.set()
                    self.status.update(modo="câmera em uso pelo cadastro", presentes=[])
                    time.sleep(0.3)
                    continue
                if self.pausado:
                    self._liberar_camera()
                    self.status.update(modo="pausado", presentes=[])
                    time.sleep(0.3)
                    continue

                if inicio < self._carencia_ate:
                    frame, rostos = None, []
                elif self._sessao_bloqueada(inicio):
                    frame, rostos = self._ciclo_bloqueado(inicio)
                    fps = self.cfg["fps_durante_bloqueio"]
                    if frame is None:
                        fps = 0.5
                else:
                    frame, rostos = self._ciclo_desbloqueado(inicio)

                if self.preview_ativo and frame is not None:
                    p = desenhar(frame.copy(), rostos)
                    self.frame_preview = cv2.resize(p, (320, int(320 * p.shape[0] / p.shape[1])))

                if inicio >= self._prox_mem:
                    self.status["ram"] = self.memoria.checar(self.visao, self.cfg)
                    self.status["economia"] = self.memoria.nivel
                    self._prox_mem = inicio + 10
                if inicio >= self._prox_limpeza:
                    n = self.banco.limpar_antigos(self.cfg["dias_retencao_fotos"])
                    if n:
                        log.info("Retenção: %d evento(s) antigo(s) apagado(s)", n)
                    self._prox_limpeza = inicio + 6 * 3600
            except Exception as e:  # nunca deixa a thread morrer
                log.error("Erro no motor: %s", e)
                self.status.update(modo="erro", erro=str(e))
                self._liberar_camera()
                time.sleep(3)
                continue

            espera = 1.0 / fps - (time.time() - inicio)
            if espera > 0:
                self._parar.wait(espera)

        sistema.manter_tela_ligada(False)
        if not self.tela_ligada:
            sistema.ligar_tela()
        self._liberar_camera()
        log.info("Motor encerrado")
