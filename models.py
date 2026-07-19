from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Familia(db.Model):
    __tablename__ = "familias"

    id = db.Column(db.Integer, primary_key=True)
    prontuario_familiar = db.Column(db.String(50), unique=True, nullable=False, index=True)
    data_cadastro = db.Column(db.Date, default=date.today, nullable=False)
    unidade_referencia = db.Column(db.String(120))
    tecnico_referencia = db.Column(db.String(120))

    cep = db.Column(db.String(10))
    logradouro = db.Column(db.String(200))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(120))
    bairro = db.Column(db.String(120))
    cidade = db.Column(db.String(120))
    uf = db.Column(db.String(2))
    ponto_referencia = db.Column(db.String(200))
    zona = db.Column(db.String(30))

    tipo_moradia = db.Column(db.String(50))
    situacao_moradia = db.Column(db.String(50))
    material_construcao = db.Column(db.String(80))
    numero_comodos = db.Column(db.Integer)
    numero_dormitorios = db.Column(db.Integer)
    tem_agua_encanada = db.Column(db.Boolean, default=False)
    tem_esgoto = db.Column(db.Boolean, default=False)
    tem_energia_eletrica = db.Column(db.Boolean, default=False)
    tem_coleta_lixo = db.Column(db.Boolean, default=False)
    tem_banheiro = db.Column(db.Boolean, default=False)

    renda_familiar_total = db.Column(db.Float, default=0.0)
    renda_per_capita = db.Column(db.Float, default=0.0)
    cad_unico = db.Column(db.String(50))
    nis_responsavel = db.Column(db.String(20))

    prog_bolsa_familia = db.Column(db.Boolean, default=False)
    valor_bolsa_familia = db.Column(db.Float, default=0.0)
    prog_bpc = db.Column(db.Boolean, default=False)
    prog_beneficios_eventuais = db.Column(db.Boolean, default=False)
    outros_programas = db.Column(db.Text)

    em_paif = db.Column(db.Boolean, default=False)
    em_paefi = db.Column(db.Boolean, default=False)
    medida_socioeducativa = db.Column(db.Boolean, default=False)
    servico_convivencia = db.Column(db.Boolean, default=False)

    vulnerabilidades = db.Column(db.Text)
    observacoes = db.Column(db.Text)

    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    membros = db.relationship("Membro", back_populates="familia", cascade="all, delete-orphan", lazy="dynamic")
    atendimentos = db.relationship("Atendimento", back_populates="familia", cascade="all, delete-orphan", lazy="dynamic")
    encaminhamentos = db.relationship("Encaminhamento", back_populates="familia", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def responsavel(self):
        return self.membros.filter_by(parentesco="Responsável Familiar").first()

    @property
    def total_membros(self):
        return self.membros.count()

    def recalcular_renda_per_capita(self):
        total = 0.0
        count = self.membros.count()
        for m in self.membros:
            total += m.renda_individual or 0.0
        if self.valor_bolsa_familia:
            total += self.valor_bolsa_familia
        self.renda_familiar_total = total
        self.renda_per_capita = (total / count) if count > 0 else 0.0


class Membro(db.Model):
    __tablename__ = "membros"

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey("familias.id"), nullable=False, index=True)

    prontuario_individual = db.Column(db.String(50), unique=True, index=True)
    nome_completo = db.Column(db.String(200), nullable=False)
    nome_social = db.Column(db.String(200))
    parentesco = db.Column(db.String(60))
    data_nascimento = db.Column(db.Date)
    sexo = db.Column(db.String(20))
    identidade_genero = db.Column(db.String(60))
    orientacao_sexual = db.Column(db.String(60))
    raca_cor = db.Column(db.String(30))
    nacionalidade = db.Column(db.String(50), default="Brasileira")
    naturalidade_cidade = db.Column(db.String(120))
    naturalidade_uf = db.Column(db.String(2))
    estado_civil = db.Column(db.String(30))

    cpf = db.Column(db.String(14), index=True)
    rg = db.Column(db.String(20))
    rg_orgao_emissor = db.Column(db.String(20))
    nis = db.Column(db.String(20))
    titulo_eleitor = db.Column(db.String(20))
    certidao_nascimento = db.Column(db.String(50))
    certidao_casamento = db.Column(db.String(50))
    carteira_trabalho = db.Column(db.String(30))

    escolaridade = db.Column(db.String(60))
    frequenta_escola = db.Column(db.Boolean, default=False)
    nome_escola = db.Column(db.String(200))
    serie = db.Column(db.String(30))
    turno = db.Column(db.String(20))

    ocupacao = db.Column(db.String(120))
    situacao_trabalho = db.Column(db.String(60))
    renda_individual = db.Column(db.Float, default=0.0)
    origem_renda = db.Column(db.String(120))

    tem_deficiencia = db.Column(db.Boolean, default=False)
    tipo_deficiencia = db.Column(db.String(200))
    cid = db.Column(db.String(20))
    recebe_bpc = db.Column(db.Boolean, default=False)
    usa_medicacao_continua = db.Column(db.Boolean, default=False)
    medicacoes = db.Column(db.Text)
    problemas_saude = db.Column(db.Text)

    gestante = db.Column(db.Boolean, default=False)
    data_provavel_parto = db.Column(db.Date)
    lactante = db.Column(db.Boolean, default=False)

    grupo_tradicional = db.Column(db.String(60))
    situacao_rua = db.Column(db.Boolean, default=False)
    lgbtqia = db.Column(db.Boolean, default=False)
    imigrante = db.Column(db.Boolean, default=False)
    trabalho_infantil = db.Column(db.Boolean, default=False)
    exploracao_sexual = db.Column(db.Boolean, default=False)
    violencia_domestica = db.Column(db.Boolean, default=False)
    uso_substancias = db.Column(db.Boolean, default=False)
    cumpre_medida_socioeducativa = db.Column(db.Boolean, default=False)

    telefone = db.Column(db.String(20))
    email = db.Column(db.String(120))

    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    data_cadastro = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    familia = db.relationship("Familia", back_populates="membros")
    evolucoes = db.relationship("EvolucaoProntuario", back_populates="membro", cascade="all, delete-orphan", lazy="dynamic", order_by="EvolucaoProntuario.data_evolucao.desc()")
    atendimentos_individuais = db.relationship("Atendimento", back_populates="membro", lazy="dynamic")

    @property
    def idade(self):
        if not self.data_nascimento:
            return None
        today = date.today()
        return today.year - self.data_nascimento.year - (
            (today.month, today.day) < (self.data_nascimento.month, self.data_nascimento.day)
        )

    @property
    def faixa_etaria(self):
        i = self.idade
        if i is None:
            return "Sem informação"
        if i < 6: return "Primeira Infância (0-5)"
        if i < 12: return "Infância (6-11)"
        if i < 18: return "Adolescente (12-17)"
        if i < 30: return "Jovem (18-29)"
        if i < 60: return "Adulto (30-59)"
        return "Idoso (60+)"


class EvolucaoProntuario(db.Model):
    __tablename__ = "evolucoes_prontuario"

    id = db.Column(db.Integer, primary_key=True)
    membro_id = db.Column(db.Integer, db.ForeignKey("membros.id"), nullable=False, index=True)
    data_evolucao = db.Column(db.Date, default=date.today, nullable=False)
    hora_evolucao = db.Column(db.Time)
    tipo_evolucao = db.Column(db.String(60))
    tecnico_responsavel = db.Column(db.String(120))
    local = db.Column(db.String(120))

    descricao = db.Column(db.Text, nullable=False)
    conduta = db.Column(db.Text)
    encaminhamentos = db.Column(db.Text)
    proximos_passos = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    membro = db.relationship("Membro", back_populates="evolucoes")


class Atendimento(db.Model):
    __tablename__ = "atendimentos"

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey("familias.id"), nullable=False, index=True)
    membro_id = db.Column(db.Integer, db.ForeignKey("membros.id"), nullable=True, index=True)

    data_atendimento = db.Column(db.Date, default=date.today, nullable=False)
    hora_atendimento = db.Column(db.Time)
    tipo_atendimento = db.Column(db.String(80))
    modalidade = db.Column(db.String(40))
    unidade = db.Column(db.String(120))
    tecnico_responsavel = db.Column(db.String(120))

    demanda_apresentada = db.Column(db.Text)
    parecer_tecnico = db.Column(db.Text)
    procedimentos = db.Column(db.Text)
    situacao = db.Column(db.String(40), default="Concluído")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    familia = db.relationship("Familia", back_populates="atendimentos")
    membro = db.relationship("Membro", back_populates="atendimentos_individuais")


class Encaminhamento(db.Model):
    __tablename__ = "encaminhamentos"

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey("familias.id"), nullable=False, index=True)
    membro_id = db.Column(db.Integer, db.ForeignKey("membros.id"), nullable=True)

    data_encaminhamento = db.Column(db.Date, default=date.today, nullable=False)
    orgao_destino = db.Column(db.String(200), nullable=False)
    setor = db.Column(db.String(120))
    motivo = db.Column(db.Text)
    profissional_referencia = db.Column(db.String(120))

    contra_referencia = db.Column(db.Boolean, default=False)
    data_contra_referencia = db.Column(db.Date)
    resultado = db.Column(db.Text)
    status = db.Column(db.String(40), default="Pendente")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    familia = db.relationship("Familia", back_populates="encaminhamentos")


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cargo = db.Column(db.String(80))
    registro_profissional = db.Column(db.String(50))
    email = db.Column(db.String(120), unique=True)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
