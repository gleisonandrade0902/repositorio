"""Configuração compartilhada (config.json) + PIN do painel."""
import hashlib
import json
import os
import secrets
import threading
from pathlib import Path

BASE = Path(__file__).parent
ARQ_CONFIG = BASE / "config.json"
PASTA_DADOS = BASE / "dados"
PASTA_CAPTURAS = BASE / "capturas"
ARQ_BANCO = PASTA_DADOS / "sentinela.db"
# Arquivo escrito pela tarefa agendada do Windows a cada falha de logon (evento 4625).
ARQ_FALHAS_LOGIN = Path(os.environ.get("ProgramData", "/tmp")) / "SentinelaTela" / "falhas_login.log"

PADRAO = {
    # Câmera / desempenho
    "camera_indice": 0,
    "fps_verificacao": 3,
    "fps_durante_bloqueio": 2,
    "largura_processamento": 320,
    "limite_memoria_mb": 300,
    # Reconhecimento
    "limiar_reconhecimento": 0.40,
    "exigir_olhar_para_tela": True,
    "yaw_max": 0.35,
    "amostras_cadastro": 25,
    # Tempos
    "segundos_para_desligar_tela": 8,
    "minutos_para_bloquear": 5,
    # Segurança
    "bloquear_se_estranho": True,
    "verificacoes_para_estranho": 4,
    "bloquear_estranho_mesmo_com_dono": False,
    "vigiar_durante_bloqueio": True,
    "capturar_fotos": True,
    "intervalo_entre_capturas_s": 30,
    "dias_retencao_fotos": 30,
    "alerta_ao_desbloquear": True,
    # Sistema
    "iniciar_com_sistema": False,
    "pin_hash": "",
    "pin_sal": "",
}

_trava = threading.Lock()


def carregar():
    cfg = dict(PADRAO)
    if ARQ_CONFIG.exists():
        try:
            cfg.update(json.loads(ARQ_CONFIG.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass  # arquivo corrompido: usa padrão e regrava abaixo
    salvar(cfg)
    return cfg


def salvar(cfg):
    with _trava:
        tmp = ARQ_CONFIG.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, ARQ_CONFIG)  # gravação atômica


def _hash(pin, sal):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), 200_000).hex()


def definir_pin(cfg, pin):
    if not pin:
        cfg["pin_hash"] = cfg["pin_sal"] = ""
    else:
        cfg["pin_sal"] = secrets.token_hex(16)
        cfg["pin_hash"] = _hash(pin, cfg["pin_sal"])


def tem_pin(cfg):
    return bool(cfg.get("pin_hash"))


def conferir_pin(cfg, pin):
    if not tem_pin(cfg):
        return True
    return secrets.compare_digest(_hash(pin, cfg["pin_sal"]), cfg["pin_hash"])
