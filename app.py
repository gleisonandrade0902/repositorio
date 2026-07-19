import io
import os
from datetime import datetime, date, time
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort, jsonify
from sqlalchemy import or_, func
from models import db, Familia, Membro, EvolucaoProntuario, Atendimento, Encaminhamento, Usuario


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "gesuas-local-dev-key-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'gesuas_local.db')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_filters(app)
    register_routes(app)
    return app


def register_filters(app):
    @app.template_filter("data_br")
    def data_br(value):
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y %H:%M")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        return value

    @app.template_filter("moeda")
    def moeda(value):
        try:
            v = float(value or 0)
        except (TypeError, ValueError):
            v = 0.0
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_filter("sim_nao")
    def sim_nao(value):
        return "Sim" if value else "Não"


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


def parse_float(value):
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return 0.0


def parse_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def form_bool(form, key):
    return form.get(key) in ("on", "1", "true", "True")


def register_routes(app):

    @app.route("/")
    def index():
        stats = {
            "familias": Familia.query.filter_by(ativo=True).count(),
            "membros": Membro.query.filter_by(ativo=True).count(),
            "atendimentos_mes": Atendimento.query.filter(
                Atendimento.data_atendimento >= date.today().replace(day=1)
            ).count(),
            "encaminhamentos_abertos": Encaminhamento.query.filter_by(status="Pendente").count(),
        }
        ultimas_familias = Familia.query.order_by(Familia.created_at.desc()).limit(5).all()
        ultimas_evolucoes = EvolucaoProntuario.query.order_by(EvolucaoProntuario.created_at.desc()).limit(8).all()
        return render_template("index.html", stats=stats, ultimas_familias=ultimas_familias, ultimas_evolucoes=ultimas_evolucoes)

    # ------------- FAMÍLIAS -------------

    @app.route("/familias")
    def familias_list():
        q = request.args.get("q", "").strip()
        query = Familia.query
        if q:
            like = f"%{q}%"
            query = query.outerjoin(Membro).filter(
                or_(
                    Familia.prontuario_familiar.ilike(like),
                    Familia.cad_unico.ilike(like),
                    Familia.nis_responsavel.ilike(like),
                    Familia.bairro.ilike(like),
                    Membro.nome_completo.ilike(like),
                    Membro.cpf.ilike(like),
                )
            ).distinct()
        familias = query.order_by(Familia.created_at.desc()).all()
        return render_template("familias/list.html", familias=familias, q=q)

    @app.route("/familias/nova", methods=["GET", "POST"])
    def familia_nova():
        if request.method == "POST":
            f = Familia()
            _preencher_familia(f, request.form)
            if not f.prontuario_familiar:
                ultimo = db.session.query(func.max(Familia.id)).scalar() or 0
                f.prontuario_familiar = f"FAM-{(ultimo + 1):06d}"
            db.session.add(f)
            db.session.commit()
            flash("Família cadastrada com sucesso.", "success")
            return redirect(url_for("familia_detalhe", familia_id=f.id))
        return render_template("familias/form.html", familia=None)

    @app.route("/familias/<int:familia_id>")
    def familia_detalhe(familia_id):
        familia = Familia.query.get_or_404(familia_id)
        return render_template("familias/detalhe.html", familia=familia)

    @app.route("/familias/<int:familia_id>/editar", methods=["GET", "POST"])
    def familia_editar(familia_id):
        familia = Familia.query.get_or_404(familia_id)
        if request.method == "POST":
            _preencher_familia(familia, request.form)
            familia.recalcular_renda_per_capita()
            db.session.commit()
            flash("Família atualizada.", "success")
            return redirect(url_for("familia_detalhe", familia_id=familia.id))
        return render_template("familias/form.html", familia=familia)

    @app.route("/familias/<int:familia_id>/excluir", methods=["POST"])
    def familia_excluir(familia_id):
        familia = Familia.query.get_or_404(familia_id)
        db.session.delete(familia)
        db.session.commit()
        flash("Família removida.", "warning")
        return redirect(url_for("familias_list"))

    def _preencher_familia(f, form):
        f.prontuario_familiar = form.get("prontuario_familiar") or f.prontuario_familiar
        f.data_cadastro = parse_date(form.get("data_cadastro")) or f.data_cadastro or date.today()
        f.unidade_referencia = form.get("unidade_referencia")
        f.tecnico_referencia = form.get("tecnico_referencia")

        for field in ["cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf",
                      "ponto_referencia", "zona", "tipo_moradia", "situacao_moradia",
                      "material_construcao", "cad_unico", "nis_responsavel",
                      "outros_programas", "vulnerabilidades", "observacoes"]:
            setattr(f, field, form.get(field))

        f.numero_comodos = parse_int(form.get("numero_comodos"))
        f.numero_dormitorios = parse_int(form.get("numero_dormitorios"))

        for b in ["tem_agua_encanada", "tem_esgoto", "tem_energia_eletrica",
                  "tem_coleta_lixo", "tem_banheiro",
                  "prog_bolsa_familia", "prog_bpc", "prog_beneficios_eventuais",
                  "em_paif", "em_paefi", "medida_socioeducativa", "servico_convivencia"]:
            setattr(f, b, form_bool(form, b))

        f.valor_bolsa_familia = parse_float(form.get("valor_bolsa_familia"))
        f.renda_familiar_total = parse_float(form.get("renda_familiar_total"))
        f.recalcular_renda_per_capita()

    # ------------- MEMBROS -------------

    @app.route("/familias/<int:familia_id>/membros/novo", methods=["GET", "POST"])
    def membro_novo(familia_id):
        familia = Familia.query.get_or_404(familia_id)
        if request.method == "POST":
            m = Membro(familia_id=familia.id)
            _preencher_membro(m, request.form)
            if not m.prontuario_individual:
                ultimo = db.session.query(func.max(Membro.id)).scalar() or 0
                m.prontuario_individual = f"IND-{(ultimo + 1):06d}"
            db.session.add(m)
            db.session.commit()
            familia.recalcular_renda_per_capita()
            db.session.commit()
            flash("Membro cadastrado.", "success")
            return redirect(url_for("membro_detalhe", membro_id=m.id))
        return render_template("membros/form.html", membro=None, familia=familia)

    @app.route("/membros/<int:membro_id>")
    def membro_detalhe(membro_id):
        membro = Membro.query.get_or_404(membro_id)
        evolucoes = membro.evolucoes.all()
        atendimentos = membro.atendimentos_individuais.order_by(Atendimento.data_atendimento.desc()).all()
        return render_template("membros/detalhe.html", membro=membro, evolucoes=evolucoes, atendimentos=atendimentos)

    @app.route("/membros/<int:membro_id>/editar", methods=["GET", "POST"])
    def membro_editar(membro_id):
        membro = Membro.query.get_or_404(membro_id)
        if request.method == "POST":
            _preencher_membro(membro, request.form)
            db.session.commit()
            membro.familia.recalcular_renda_per_capita()
            db.session.commit()
            flash("Membro atualizado.", "success")
            return redirect(url_for("membro_detalhe", membro_id=membro.id))
        return render_template("membros/form.html", membro=membro, familia=membro.familia)

    @app.route("/membros/<int:membro_id>/excluir", methods=["POST"])
    def membro_excluir(membro_id):
        membro = Membro.query.get_or_404(membro_id)
        familia_id = membro.familia_id
        familia = membro.familia
        db.session.delete(membro)
        db.session.commit()
        familia.recalcular_renda_per_capita()
        db.session.commit()
        flash("Membro removido.", "warning")
        return redirect(url_for("familia_detalhe", familia_id=familia_id))

    def _preencher_membro(m, form):
        for field in ["prontuario_individual", "nome_completo", "nome_social", "parentesco",
                      "sexo", "identidade_genero", "orientacao_sexual", "raca_cor",
                      "nacionalidade", "naturalidade_cidade", "naturalidade_uf", "estado_civil",
                      "cpf", "rg", "rg_orgao_emissor", "nis", "titulo_eleitor",
                      "certidao_nascimento", "certidao_casamento", "carteira_trabalho",
                      "escolaridade", "nome_escola", "serie", "turno",
                      "ocupacao", "situacao_trabalho", "origem_renda",
                      "tipo_deficiencia", "cid", "medicacoes", "problemas_saude",
                      "grupo_tradicional", "telefone", "email", "observacoes"]:
            setattr(m, field, form.get(field))

        m.data_nascimento = parse_date(form.get("data_nascimento"))
        m.data_provavel_parto = parse_date(form.get("data_provavel_parto"))
        m.renda_individual = parse_float(form.get("renda_individual"))

        for b in ["frequenta_escola", "tem_deficiencia", "recebe_bpc", "usa_medicacao_continua",
                  "gestante", "lactante", "situacao_rua", "lgbtqia", "imigrante",
                  "trabalho_infantil", "exploracao_sexual", "violencia_domestica",
                  "uso_substancias", "cumpre_medida_socioeducativa", "ativo"]:
            setattr(m, b, form_bool(form, b))

    # ------------- EVOLUÇÃO / PRONTUÁRIO -------------

    @app.route("/membros/<int:membro_id>/evolucoes/nova", methods=["GET", "POST"])
    def evolucao_nova(membro_id):
        membro = Membro.query.get_or_404(membro_id)
        if request.method == "POST":
            ev = EvolucaoProntuario(membro_id=membro.id)
            _preencher_evolucao(ev, request.form)
            db.session.add(ev)
            db.session.commit()
            flash("Evolução registrada no prontuário.", "success")
            return redirect(url_for("membro_detalhe", membro_id=membro.id) + "#prontuario")
        return render_template("evolucoes/form.html", membro=membro, evolucao=None)

    @app.route("/evolucoes/<int:evolucao_id>/editar", methods=["GET", "POST"])
    def evolucao_editar(evolucao_id):
        ev = EvolucaoProntuario.query.get_or_404(evolucao_id)
        if request.method == "POST":
            _preencher_evolucao(ev, request.form)
            db.session.commit()
            flash("Evolução atualizada.", "success")
            return redirect(url_for("membro_detalhe", membro_id=ev.membro_id) + "#prontuario")
        return render_template("evolucoes/form.html", membro=ev.membro, evolucao=ev)

    @app.route("/evolucoes/<int:evolucao_id>/excluir", methods=["POST"])
    def evolucao_excluir(evolucao_id):
        ev = EvolucaoProntuario.query.get_or_404(evolucao_id)
        membro_id = ev.membro_id
        db.session.delete(ev)
        db.session.commit()
        flash("Evolução removida.", "warning")
        return redirect(url_for("membro_detalhe", membro_id=membro_id) + "#prontuario")

    def _preencher_evolucao(ev, form):
        ev.data_evolucao = parse_date(form.get("data_evolucao")) or date.today()
        ev.hora_evolucao = parse_time(form.get("hora_evolucao"))
        for f in ["tipo_evolucao", "tecnico_responsavel", "local",
                  "descricao", "conduta", "encaminhamentos", "proximos_passos"]:
            setattr(ev, f, form.get(f))

    # ------------- ATENDIMENTOS -------------

    @app.route("/atendimentos")
    def atendimentos_list():
        atendimentos = Atendimento.query.order_by(Atendimento.data_atendimento.desc()).limit(300).all()
        return render_template("atendimentos/list.html", atendimentos=atendimentos)

    @app.route("/familias/<int:familia_id>/atendimentos/novo", methods=["GET", "POST"])
    def atendimento_novo(familia_id):
        familia = Familia.query.get_or_404(familia_id)
        if request.method == "POST":
            a = Atendimento(familia_id=familia.id)
            _preencher_atendimento(a, request.form)
            db.session.add(a)
            db.session.commit()
            flash("Atendimento registrado.", "success")
            return redirect(url_for("familia_detalhe", familia_id=familia.id) + "#atendimentos")
        return render_template("atendimentos/form.html", familia=familia, atendimento=None)

    @app.route("/atendimentos/<int:atendimento_id>/editar", methods=["GET", "POST"])
    def atendimento_editar(atendimento_id):
        a = Atendimento.query.get_or_404(atendimento_id)
        if request.method == "POST":
            _preencher_atendimento(a, request.form)
            db.session.commit()
            flash("Atendimento atualizado.", "success")
            return redirect(url_for("familia_detalhe", familia_id=a.familia_id) + "#atendimentos")
        return render_template("atendimentos/form.html", familia=a.familia, atendimento=a)

    @app.route("/atendimentos/<int:atendimento_id>/excluir", methods=["POST"])
    def atendimento_excluir(atendimento_id):
        a = Atendimento.query.get_or_404(atendimento_id)
        familia_id = a.familia_id
        db.session.delete(a)
        db.session.commit()
        flash("Atendimento removido.", "warning")
        return redirect(url_for("familia_detalhe", familia_id=familia_id) + "#atendimentos")

    def _preencher_atendimento(a, form):
        a.data_atendimento = parse_date(form.get("data_atendimento")) or date.today()
        a.hora_atendimento = parse_time(form.get("hora_atendimento"))
        a.membro_id = parse_int(form.get("membro_id"))
        for f in ["tipo_atendimento", "modalidade", "unidade", "tecnico_responsavel",
                  "demanda_apresentada", "parecer_tecnico", "procedimentos", "situacao"]:
            setattr(a, f, form.get(f))

    # ------------- ENCAMINHAMENTOS -------------

    @app.route("/familias/<int:familia_id>/encaminhamentos/novo", methods=["GET", "POST"])
    def encaminhamento_novo(familia_id):
        familia = Familia.query.get_or_404(familia_id)
        if request.method == "POST":
            e = Encaminhamento(familia_id=familia.id)
            _preencher_encaminhamento(e, request.form)
            db.session.add(e)
            db.session.commit()
            flash("Encaminhamento registrado.", "success")
            return redirect(url_for("familia_detalhe", familia_id=familia.id) + "#encaminhamentos")
        return render_template("encaminhamentos/form.html", familia=familia, encaminhamento=None)

    @app.route("/encaminhamentos/<int:enc_id>/editar", methods=["GET", "POST"])
    def encaminhamento_editar(enc_id):
        e = Encaminhamento.query.get_or_404(enc_id)
        if request.method == "POST":
            _preencher_encaminhamento(e, request.form)
            db.session.commit()
            flash("Encaminhamento atualizado.", "success")
            return redirect(url_for("familia_detalhe", familia_id=e.familia_id) + "#encaminhamentos")
        return render_template("encaminhamentos/form.html", familia=e.familia, encaminhamento=e)

    @app.route("/encaminhamentos/<int:enc_id>/excluir", methods=["POST"])
    def encaminhamento_excluir(enc_id):
        e = Encaminhamento.query.get_or_404(enc_id)
        familia_id = e.familia_id
        db.session.delete(e)
        db.session.commit()
        flash("Encaminhamento removido.", "warning")
        return redirect(url_for("familia_detalhe", familia_id=familia_id) + "#encaminhamentos")

    def _preencher_encaminhamento(e, form):
        e.data_encaminhamento = parse_date(form.get("data_encaminhamento")) or date.today()
        e.data_contra_referencia = parse_date(form.get("data_contra_referencia"))
        e.membro_id = parse_int(form.get("membro_id"))
        e.contra_referencia = form_bool(form, "contra_referencia")
        for f in ["orgao_destino", "setor", "motivo", "profissional_referencia", "resultado", "status"]:
            setattr(e, f, form.get(f))

    # ------------- RELATÓRIOS -------------

    @app.route("/relatorios")
    def relatorios_index():
        return render_template("relatorios/index.html")

    @app.route("/relatorios/familias")
    def relatorio_familias():
        familias = Familia.query.order_by(Familia.prontuario_familiar).all()
        total_pessoas = Membro.query.count()
        total_familias = len(familias)
        pobreza = sum(1 for f in familias if (f.renda_per_capita or 0) < 218)
        extrema_pobreza = sum(1 for f in familias if (f.renda_per_capita or 0) < 109)
        bolsa_familia = sum(1 for f in familias if f.prog_bolsa_familia)
        bpc = sum(1 for f in familias if f.prog_bpc)
        paif = sum(1 for f in familias if f.em_paif)
        paefi = sum(1 for f in familias if f.em_paefi)
        return render_template("relatorios/familias.html",
                               familias=familias,
                               total_pessoas=total_pessoas,
                               total_familias=total_familias,
                               pobreza=pobreza,
                               extrema_pobreza=extrema_pobreza,
                               bolsa_familia=bolsa_familia,
                               bpc=bpc,
                               paif=paif,
                               paefi=paefi,
                               agora=datetime.now())

    @app.route("/relatorios/populacional")
    def relatorio_populacional():
        membros = Membro.query.filter_by(ativo=True).all()
        faixas = {}
        sexo = {}
        raca = {}
        deficiencia = {"Com deficiência": 0, "Sem deficiência": 0}
        for m in membros:
            faixas[m.faixa_etaria] = faixas.get(m.faixa_etaria, 0) + 1
            sexo[m.sexo or "Não informado"] = sexo.get(m.sexo or "Não informado", 0) + 1
            raca[m.raca_cor or "Não informado"] = raca.get(m.raca_cor or "Não informado", 0) + 1
            if m.tem_deficiencia:
                deficiencia["Com deficiência"] += 1
            else:
                deficiencia["Sem deficiência"] += 1
        return render_template("relatorios/populacional.html",
                               total=len(membros),
                               faixas=faixas, sexo=sexo, raca=raca,
                               deficiencia=deficiencia,
                               agora=datetime.now())

    @app.route("/relatorios/vulnerabilidades")
    def relatorio_vulnerabilidades():
        campos = [
            ("Situação de rua", Membro.situacao_rua),
            ("Trabalho infantil", Membro.trabalho_infantil),
            ("Exploração sexual", Membro.exploracao_sexual),
            ("Violência doméstica", Membro.violencia_domestica),
            ("Uso de substâncias", Membro.uso_substancias),
            ("Medida socioeducativa", Membro.cumpre_medida_socioeducativa),
            ("Gestante", Membro.gestante),
            ("Deficiência", Membro.tem_deficiencia),
        ]
        dados = []
        for label, coluna in campos:
            qtd = Membro.query.filter(coluna == True).count()
            dados.append((label, qtd))
        return render_template("relatorios/vulnerabilidades.html", dados=dados, agora=datetime.now())

    @app.route("/relatorios/familia/<int:familia_id>")
    def relatorio_familia_individual(familia_id):
        familia = Familia.query.get_or_404(familia_id)
        return render_template("relatorios/familia_individual.html", familia=familia, agora=datetime.now())

    @app.route("/relatorios/prontuario/<int:membro_id>")
    def relatorio_prontuario(membro_id):
        membro = Membro.query.get_or_404(membro_id)
        evolucoes = membro.evolucoes.all()
        return render_template("relatorios/prontuario.html", membro=membro, evolucoes=evolucoes, agora=datetime.now())

    @app.route("/relatorios/atendimentos")
    def relatorio_atendimentos():
        inicio = parse_date(request.args.get("inicio"))
        fim = parse_date(request.args.get("fim"))
        q = Atendimento.query
        if inicio:
            q = q.filter(Atendimento.data_atendimento >= inicio)
        if fim:
            q = q.filter(Atendimento.data_atendimento <= fim)
        atendimentos = q.order_by(Atendimento.data_atendimento.desc()).all()

        por_tipo = {}
        por_tecnico = {}
        for a in atendimentos:
            por_tipo[a.tipo_atendimento or "Não informado"] = por_tipo.get(a.tipo_atendimento or "Não informado", 0) + 1
            por_tecnico[a.tecnico_responsavel or "Não informado"] = por_tecnico.get(a.tecnico_responsavel or "Não informado", 0) + 1
        return render_template("relatorios/atendimentos.html",
                               atendimentos=atendimentos,
                               por_tipo=por_tipo,
                               por_tecnico=por_tecnico,
                               inicio=inicio, fim=fim,
                               agora=datetime.now())

    # ------------- API/UTILITÁRIOS -------------

    @app.route("/api/familias/<int:familia_id>/membros")
    def api_familia_membros(familia_id):
        familia = Familia.query.get_or_404(familia_id)
        return jsonify([
            {"id": m.id, "nome": m.nome_completo, "parentesco": m.parentesco}
            for m in familia.membros
        ])

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
