"""
Detecção (YuNet) e reconhecimento facial (SFace) usando apenas OpenCV.

Por que esses modelos: juntos somam ~37 MB em disco e rodam em CPU com
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
    similaridade: float   # cosseno com o dono (−1..1); 0 se não comparado
    eh_dono: bool
    olhando: bool         # rosto razoavelmente frontal


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
        self.assinaturas_dono = None  # np.ndarray (N, 128), L2-normalizado

    # ------------------------------------------------------------------
    def carregar_dono(self, caminho: Path):
        emb = np.load(caminho).astype(np.float32)
        self.assinaturas_dono = emb / np.linalg.norm(emb, axis=1, keepdims=True)

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
        desvio = abs(nx - (ox1 + ox2) / 2) / dist_olhos
        return desvio <= yaw_max

    def analisar(self, frame, max_rostos=3):
        pequeno, escala, faces = self.detectar(frame)
        # Prioriza os maiores rostos (mais próximos da tela)
        if len(faces) > max_rostos:
            faces = faces[np.argsort(-faces[:, 2] * faces[:, 3])[:max_rostos]]
        rostos = []
        for f in faces:
            sim = 0.0
            if self.assinaturas_dono is not None:
                emb = self.assinatura(pequeno, f)
                sim = float(np.max(self.assinaturas_dono @ emb))
            caixa = tuple(int(v / escala) for v in f[:4])
            rostos.append(Rosto(caixa, sim, sim >= self.limiar_rec,
                                bool(self._olhando(f, self.yaw_max))))
        return rostos
