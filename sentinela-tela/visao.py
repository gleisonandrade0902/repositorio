"""
Detecção (YuNet) e reconhecimento facial (SFace) usando apenas OpenCV.

Por que esses modelos: juntos somam ~39 MB em disco e rodam em CPU com
1 thread, mantendo o processo bem abaixo de 300 MB de RAM. Alternativas
como dlib/face_recognition ou DeepFace (TensorFlow) passam de 500 MB.
"""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

PASTA_MODELOS = Path(__file__).parent / "modelos"
MODELO_DETECTOR = PASTA_MODELOS / "face_detection_yunet_2023mar.onnx"
MODELO_RECONHECEDOR = PASTA_MODELOS / "face_recognition_sface_2021dec.onnx"


@dataclass
class Rosto:
    caixa: tuple          # x, y, w, h (na escala do frame original)
    similaridade: float   # melhor cosseno contra as pessoas cadastradas
    autorizado: bool
    olhando: bool         # rosto razoavelmente frontal
    nome: str = ""        # nome da pessoa reconhecida ("" = desconhecido)
    pessoa_id: int = 0


class Visao:
    def __init__(self, largura_processamento=320, limiar_deteccao=0.8,
                 limiar_reconhecimento=0.40, yaw_max=0.35):
        if not MODELO_DETECTOR.exists() or not MODELO_RECONHECEDOR.exists():
            raise FileNotFoundError(
                "Modelos não encontrados. Rode primeiro: python baixar_modelos.py")
        cv2.setNumThreads(1)  # menos RAM e CPU; 2-5 fps não precisa de mais
        self.largura = largura_processamento
        self.limiar_rec = limiar_reconhecimento
        self.yaw_max = yaw_max
        self.detector = cv2.FaceDetectorYN.create(
            str(MODELO_DETECTOR), "", (320, 240), limiar_deteccao, 0.3, 20)
        self.reconhecedor = cv2.FaceRecognizerSF.create(str(MODELO_RECONHECEDOR), "")
        self._matriz = np.empty((0, 128), np.float32)  # todas as assinaturas empilhadas
        self._rotulos = np.empty(0, np.int64)          # índice da pessoa de cada linha
        self._pessoas = []                             # [(id, nome)]

    # ------------------------------------------------------------------
    def carregar_pessoas(self, pessoas):
        """pessoas: [(id, nome, ndarray(N,128))]"""
        mats, rot, lista = [], [], []
        for i, (pid, nome, emb) in enumerate(pessoas):
            emb = emb.astype(np.float32)
            mats.append(emb / np.linalg.norm(emb, axis=1, keepdims=True))
            rot.append(np.full(len(emb), i))
            lista.append((pid, nome))
        self._matriz = np.vstack(mats) if mats else np.empty((0, 128), np.float32)
        self._rotulos = np.concatenate(rot) if rot else np.empty(0, np.int64)
        self._pessoas = lista

    @property
    def total_pessoas(self):
        return len(self._pessoas)

    def _reduzir(self, frame):
        h, w = frame.shape[:2]
        escala = self.largura / float(w)
        if escala < 1.0:
            frame = cv2.resize(frame, (self.largura, int(h * escala)),
                               interpolation=cv2.INTER_AREA)
        else:
            escala = 1.0
        return frame, escala

    def detectar(self, frame):
        """Retorna (frame_reduzido, escala, faces[N,15])."""
        pequeno, escala = self._reduzir(frame)
        h, w = pequeno.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(pequeno)
        if faces is None:
            faces = np.empty((0, 15), np.float32)
        return pequeno, escala, faces

    def assinatura(self, pequeno, face):
        alinhado = self.reconhecedor.alignCrop(pequeno, face)
        emb = self.reconhecedor.feature(alinhado).flatten()
        return emb / (np.linalg.norm(emb) + 1e-9)

    @staticmethod
    def _olhando(face, yaw_max):
        # Landmarks YuNet: olho dir (4,5), olho esq (6,7), nariz (8,9).
        # Se o nariz sair muito do meio entre os olhos, a cabeça está virada.
        ox1, ox2, nx = face[4], face[6], face[8]
        dist_olhos = abs(ox2 - ox1)
        if dist_olhos < 1:
            return False
        return bool(abs(nx - (ox1 + ox2) / 2) / dist_olhos <= yaw_max)

    def analisar(self, frame, max_rostos=3):
        pequeno, escala, faces = self.detectar(frame)
        # Prioriza os maiores rostos (mais próximos da tela)
        if len(faces) > max_rostos:
            faces = faces[np.argsort(-faces[:, 2] * faces[:, 3])[:max_rostos]]
        rostos = []
        for f in faces:
            sim, nome, pid = 0.0, "", 0
            if len(self._matriz):
                sims = self._matriz @ self.assinatura(pequeno, f)
                k = int(np.argmax(sims))
                sim = float(sims[k])
                if sim >= self.limiar_rec:
                    pid, nome = self._pessoas[self._rotulos[k]]
            caixa = tuple(int(v / escala) for v in f[:4])
            rostos.append(Rosto(caixa, sim, bool(pid), self._olhando(f, self.yaw_max), nome, pid))
        return rostos


def desenhar(frame, rostos):
    """Marca os rostos no frame (usado no preview e nas fotos de evidência)."""
    for r in rostos:
        x, y, w, h = r.caixa
        cor = (60, 200, 60) if r.autorizado else (40, 40, 230)
        cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)
        txt = f"{r.nome or 'DESCONHECIDO'} {r.similaridade:.2f}" + ("" if r.olhando else " (virado)")
        cv2.putText(frame, txt, (x, max(14, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 1, cv2.LINE_AA)
    return frame
