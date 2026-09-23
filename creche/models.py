import json
from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


LINK_APTO_PADRAO = "https://forms.gle/uZ9oi6YXtaJ81nEb9"
LINK_MENOR_PADRAO = "https://forms.gle/VkN9rkHUMxP1CqLdA"


class Configuracao(db.Model):
    """Parâmetros da página publicada (registro único, id=1)."""

    __tablename__ = "configuracao"

    id = db.Column(db.Integer, primary_key=True)
    nome_creche = db.Column(db.String(200), nullable=False, default="Creche Municipal Dona Léa")
    data_corte = db.Column(db.Date, nullable=False, default=lambda: date(date.today().year, 3, 31))
    link_apto = db.Column(db.String(500), nullable=False, default=LINK_APTO_PADRAO)
    link_menor = db.Column(db.String(500), nullable=False, default=LINK_MENOR_PADRAO)
    responsavel_padrao = db.Column(db.String(120))

    ultimo_arquivo = db.Column(db.String(255))
    ultima_importacao = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    @classmethod
    def atual(cls):
        cfg = db.session.get(cls, 1)
        if cfg is None:
            cfg = cls(id=1)
            db.session.add(cfg)
            db.session.commit()
        return cfg


class Aluno(db.Model):
    """Lista atual de inscritos (espelho da última planilha importada + ajustes manuais)."""

    __tablename__ = "alunos"

    id = db.Column(db.Integer, primary_key=True)
    ordem = db.Column(db.Integer, nullable=False, default=0, index=True)
    inscricao = db.Column(db.String(50), nullable=False, default="-")
    nome = db.Column(db.String(200), nullable=False)
    # "DD/MM/AAAA" ou "**/MM/AAAA" — a página sempre publica mascarado (LGPD).
    nascimento = db.Column(db.String(10), nullable=False, default="")
    situacao = db.Column(db.String(300), nullable=False, default="")
    data_inscricao = db.Column(db.String(10), nullable=False, default="")
    observacao = db.Column(db.Text, nullable=False, default="")

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "inscricao": self.inscricao,
            "nome": self.nome,
            "nascimento": self.nascimento,
            "situacao": self.situacao,
            "data_inscricao": self.data_inscricao,
            "observacao": self.observacao,
        }


class Atualizacao(db.Model):
    """Log imutável de cada HTML gerado. Não há rota de edição/exclusão.

    Cada registro guarda a lista completa daquele momento, o HTML publicado e
    um hash encadeado com o registro anterior (qualquer alteração posterior no
    banco quebra a cadeia e aparece na verificação de integridade).
    """

    __tablename__ = "atualizacoes"

    id = db.Column(db.Integer, primary_key=True)
    gerado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    atualizado_em = db.Column(db.Date, nullable=False)
    data_corte = db.Column(db.Date, nullable=False)
    nome_creche = db.Column(db.String(200), nullable=False)
    link_apto = db.Column(db.String(500), nullable=False)
    link_menor = db.Column(db.String(500), nullable=False)
    responsavel = db.Column(db.String(120), nullable=False)
    motivo = db.Column(db.Text, nullable=False, default="")
    arquivo_origem = db.Column(db.String(255))

    total_alunos = db.Column(db.Integer, nullable=False, default=0)
    novos_json = db.Column(db.Text, nullable=False, default="[]")
    removidos_json = db.Column(db.Text, nullable=False, default="[]")
    alterados_json = db.Column(db.Text, nullable=False, default="[]")
    parametros_json = db.Column(db.Text, nullable=False, default="[]")
    snapshot_json = db.Column(db.Text, nullable=False, default="[]")

    html = db.Column(db.Text, nullable=False)
    hash_html = db.Column(db.String(64), nullable=False)
    hash_anterior = db.Column(db.String(64), nullable=False, default="")
    hash_cadeia = db.Column(db.String(64), nullable=False)

    @property
    def novos(self):
        return json.loads(self.novos_json)

    @property
    def removidos(self):
        return json.loads(self.removidos_json)

    @property
    def alterados(self):
        return json.loads(self.alterados_json)

    @property
    def parametros(self):
        return json.loads(self.parametros_json)

    @property
    def snapshot(self):
        return json.loads(self.snapshot_json)
