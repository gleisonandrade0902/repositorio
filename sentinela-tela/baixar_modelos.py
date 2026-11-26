"""Baixa os modelos ONNX oficiais do OpenCV Zoo (~37 MB no total)."""
import urllib.request
from pathlib import Path

BASE = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
MODELOS = {
    "face_detection_yunet_2023mar.onnx": BASE + "face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": BASE + "face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
pasta = Path(__file__).parent / "modelos"
pasta.mkdir(exist_ok=True)
for nome, url in MODELOS.items():
    destino = pasta / nome
    if destino.exists() and destino.stat().st_size > 100_000:
        print(f"ok  {nome} (já existe)")
        continue
    print(f"baixando {nome}...")
    urllib.request.urlretrieve(url, destino)
    if destino.stat().st_size < 100_000:  # veio página de erro/ponteiro LFS
        destino.unlink()
        raise SystemExit(f"Download inválido de {nome}. Baixe manualmente: {url}")
    print(f"ok  {nome} ({destino.stat().st_size/1e6:.1f} MB)")
