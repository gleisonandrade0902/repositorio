"""Persistência em SQLite: pessoas autorizadas e eventos/tentativas de acesso."""
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from config import ARQ_BANCO, PASTA_CAPTURAS, BASE

# Tipos de evento
INTRUSO_SESSAO = "intruso_sessao"      # estranho diante do PC desbloqueado -> bloqueou
INTRUSO_BLOQUEIO = "intruso_bloqueio"  # estranho diante da tela de bloqueio
SENHA_INCORRETA = "senha_incorreta"    # Windows registrou falha de logon (4625)
BLOQUEIO = "bloqueio"
SISTEMA = "sistema"

ROTULOS = {
    INTRUSO_SESSAO: "Pessoa não cadastrada usando o PC",
    INTRUSO_BLOQUEIO: "Pessoa não cadastrada na tela de bloqueio",
    SENHA_INCORRETA: "Senha incorreta digitada",
    BLOQUEIO: "Bloqueio",
    SISTEMA: "Sistema",
}
TIPOS_TENTATIVA = (INTRUSO_SESSAO, INTRUSO_BLOQUEIO, SENHA_INCORRETA)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS pessoas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    assinaturas BLOB NOT NULL,          -- float32 (N,128); nenhuma foto é guardada
    amostras INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora TEXT NOT NULL,
    tipo TEXT NOT NULL,
    descricao TEXT,
    foto TEXT,                          -- caminho relativo à pasta do programa
    similaridade REAL,
    visto INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_eventos_data ON eventos(data_hora);
"""


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Banco:
    def __init__(self, caminho: Path = ARQ_BANCO):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        PASTA_CAPTURAS.mkdir(exist_ok=True)
        self._trava = threading.Lock()
        self.con = sqlite3.connect(caminho, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        self.con.execute("PRAGMA journal_mode=WAL")

    def _q(self, sql, args=(), commit=False):
        with self._trava:
            cur = self.con.execute(sql, args)
            if commit:
                self.con.commit()
                return cur.lastrowid
            return cur.fetchall()

    # ---------------- pessoas ----------------
    def adicionar_pessoa(self, nome, assinaturas: np.ndarray):
        a = assinaturas.astype(np.float32)
        return self._q("INSERT INTO pessoas(nome,criado_em,assinaturas,amostras) VALUES(?,?,?,?)",
                       (nome, agora(), a.tobytes(), len(a)), commit=True)

    def atualizar_assinaturas(self, pid, assinaturas):
        a = assinaturas.astype(np.float32)
        self._q("UPDATE pessoas SET assinaturas=?, amostras=? WHERE id=?",
                (a.tobytes(), len(a), pid), commit=True)

    def renomear_pessoa(self, pid, nome):
        self._q("UPDATE pessoas SET nome=? WHERE id=?", (nome, pid), commit=True)

    def ativar_pessoa(self, pid, ativo):
        self._q("UPDATE pessoas SET ativo=? WHERE id=?", (int(ativo), pid), commit=True)

    def excluir_pessoa(self, pid):
        self._q("DELETE FROM pessoas WHERE id=?", (pid,), commit=True)

    def listar_pessoas(self):
        return self._q("SELECT id,nome,criado_em,ativo,amostras FROM pessoas ORDER BY nome")

    def assinaturas_ativas(self):
        """[(id, nome, ndarray(N,128))] das pessoas ativas."""
        rows = self._q("SELECT id,nome,assinaturas FROM pessoas WHERE ativo=1")
        return [(r["id"], r["nome"], np.frombuffer(r["assinaturas"], np.float32).reshape(-1, 128))
                for r in rows]

    # ---------------- eventos ----------------
    def registrar(self, tipo, descricao="", foto=None, similaridade=None, visto=False):
        rel = str(Path(foto).relative_to(BASE)) if foto else None
        return self._q("INSERT INTO eventos(data_hora,tipo,descricao,foto,similaridade,visto) "
                       "VALUES(?,?,?,?,?,?)", (agora(), tipo, descricao, rel, similaridade, int(visto)),
                       commit=True)

    def listar_eventos(self, tipos=None, limite=500):
        if tipos:
            marc = ",".join("?" * len(tipos))
            return self._q(f"SELECT * FROM eventos WHERE tipo IN ({marc}) "
                           "ORDER BY id DESC LIMIT ?", (*tipos, limite))
        return self._q("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limite,))

    def nao_vistas(self, desde_id=0):
        marc = ",".join("?" * len(TIPOS_TENTATIVA))
        return self._q(f"SELECT * FROM eventos WHERE visto=0 AND id>? AND tipo IN ({marc}) "
                       "ORDER BY id DESC", (desde_id, *TIPOS_TENTATIVA))

    def contar_tentativas_hoje(self):
        marc = ",".join("?" * len(TIPOS_TENTATIVA))
        hoje = datetime.now().strftime("%Y-%m-%d")
        return self._q(f"SELECT COUNT(*) n FROM eventos WHERE data_hora>=? AND tipo IN ({marc})",
                       (hoje, *TIPOS_TENTATIVA))[0]["n"]

    def ultimo_id(self):
        return self._q("SELECT COALESCE(MAX(id),0) m FROM eventos")[0]["m"]

    def marcar_vistos(self, ids=None):
        if ids is None:
            self._q("UPDATE eventos SET visto=1 WHERE visto=0", commit=True)
        else:
            for i in ids:
                self._q("UPDATE eventos SET visto=1 WHERE id=?", (i,), commit=True)

    def excluir_eventos(self, ids):
        for i in ids:
            row = self._q("SELECT foto FROM eventos WHERE id=?", (i,))
            if row and row[0]["foto"]:
                (BASE / row[0]["foto"]).unlink(missing_ok=True)
            self._q("DELETE FROM eventos WHERE id=?", (i,), commit=True)

    def limpar_antigos(self, dias):
        """Retenção (LGPD): apaga fotos/eventos com mais de `dias`."""
        if dias <= 0:
            return 0
        corte = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        ids = [r["id"] for r in self._q("SELECT id FROM eventos WHERE data_hora<?", (corte,))]
        self.excluir_eventos(ids)
        return len(ids)
