import csv
import io
import json
import os
import re
from datetime import date, datetime

from flask import Flask, Response, abort, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import func

from models import Aluno, Atualizacao, Configuracao, db
from planilha import (
    CABECALHOS,
    CAMPOS,
    PlanilhaInvalida,
    comparar,
    exportar_xlsx,
    formatar_data,
    importar_arquivo,
    limpar,
)
from publicacao import calcular_hash_cadeia, gerar_html, registrar_filtros, sha256, verificar_cadeia

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
RE_LINK = re.compile(r"^https://[^\s'\"<>\\]+$")


def create_app(config=None):
    app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "creche-local-dev-key-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'creche.db')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    if config:
        app.config.update(config)

    # Necessário para o modelo do IPM sair com as mesmas quebras de linha do original.
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()

    registrar_filtros(app)
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


def lista_atual():
    return [a.to_dict() for a in Aluno.query.order_by(Aluno.ordem, Aluno.id).all()]


def ultima_atualizacao():
    return Atualizacao.query.order_by(Atualizacao.id.desc()).first()


def mudancas_de_parametros(cfg, ultima):
    """O que mudou na data de corte, links e nome desde a última geração."""
    if ultima is None:
        return []
    campos = (
        ("Data de corte", ultima.data_corte.strftime("%d/%m/%Y"), cfg.data_corte.strftime("%d/%m/%Y")),
        ("Link do formulário (apto)", ultima.link_apto, cfg.link_apto),
        ("Link do formulário (menor de 18 meses)", ultima.link_menor, cfg.link_menor),
        ("Nome da creche", ultima.nome_creche, cfg.nome_creche),
    )
    return [{"campo": c, "de": de, "para": para} for c, de, para in campos if de != para]


def pendencias(cfg):
    ultima = ultima_atualizacao()
    anterior = ultima.snapshot if ultima else []
    diff = comparar(anterior, lista_atual())
    diff["parametros"] = mudancas_de_parametros(cfg, ultima)
    diff["total"] = sum(len(diff[k]) for k in ("novos", "removidos", "alterados", "parametros"))
    return ultima, diff


def caminho_importacao_pendente(app):
    return os.path.join(app.instance_path, "importacao_pendente.json")


def ler_form_aluno(form):
    nascimento, ok_nasc = formatar_data(form.get("nascimento", ""), permitir_mascara=True)
    data_insc, ok_insc = formatar_data(form.get("data_inscricao", ""))
    erros = []
    dados = {
        "inscricao": limpar(form.get("inscricao")) or "-",
        "nome": limpar(form.get("nome")),
        "nascimento": nascimento,
        "situacao": limpar(form.get("situacao")).upper(),
        "data_inscricao": data_insc,
        "observacao": limpar(form.get("observacao")),
    }
    if not dados["nome"]:
        erros.append("Informe o nome do candidato.")
    if not dados["situacao"]:
        erros.append("Informe a situação.")
    if nascimento and not ok_nasc:
        erros.append("Nascimento inválido. Use DD/MM/AAAA.")
    if data_insc and not ok_insc:
        erros.append("Data de inscrição inválida. Use DD/MM/AAAA.")
    return dados, erros


def register_routes(app):
    @app.context_processor
    def injetar_config():
        return {"cfg": Configuracao.atual()}

    # ------------------------------------------------------------------ painel
    @app.route("/")
    def index():
        cfg = Configuracao.atual()
        ultima, diff = pendencias(cfg)
        total = Aluno.query.count()
        por_situacao = (
            db.session.query(Aluno.situacao, func.count(Aluno.id))
            .group_by(Aluno.situacao)
            .order_by(func.count(Aluno.id).desc())
            .all()
        )
        return render_template(
            "painel.html",
            ultima=ultima,
            diff=diff,
            total=total,
            por_situacao=por_situacao,
            total_logs=Atualizacao.query.count(),
        )

    # ------------------------------------------------------------------ alunos
    @app.route("/alunos")
    def alunos_list():
        q = request.args.get("q", "").strip()
        consulta = Aluno.query
        if q:
            consulta = consulta.filter(Aluno.nome.ilike(f"%{q}%") | Aluno.situacao.ilike(f"%{q}%"))
        alunos = consulta.order_by(Aluno.ordem, Aluno.id).all()
        return render_template("alunos.html", alunos=alunos, q=q)

    @app.route("/alunos/novo", methods=["GET", "POST"])
    @app.route("/alunos/<int:aluno_id>/editar", methods=["GET", "POST"])
    def aluno_form(aluno_id=None):
        aluno = db.session.get(Aluno, aluno_id) if aluno_id else None
        if aluno_id and aluno is None:
            abort(404)
        if request.method == "POST":
            dados, erros = ler_form_aluno(request.form)
            if erros:
                for e in erros:
                    flash(e, "error")
                return render_template("aluno_form.html", aluno=aluno, dados=dados)
            if aluno is None:
                ordem = (db.session.query(func.max(Aluno.ordem)).scalar() or 0) + 1
                aluno = Aluno(ordem=ordem)
                db.session.add(aluno)
            for campo, valor in dados.items():
                setattr(aluno, campo, valor)
            db.session.commit()
            flash(f"Aluno '{aluno.nome}' salvo. Lembre-se de gerar o HTML para publicar.", "success")
            return redirect(url_for("alunos_list"))
        return render_template("aluno_form.html", aluno=aluno, dados=aluno.to_dict() if aluno else {})

    @app.route("/alunos/<int:aluno_id>/excluir", methods=["POST"])
    def aluno_excluir(aluno_id):
        aluno = db.session.get(Aluno, aluno_id) or abort(404)
        db.session.delete(aluno)
        db.session.commit()
        flash(f"Aluno '{aluno.nome}' removido da lista atual.", "success")
        return redirect(url_for("alunos_list"))

    @app.route("/alunos/<int:aluno_id>/mover/<direcao>", methods=["POST"])
    def aluno_mover(aluno_id, direcao):
        alunos = Aluno.query.order_by(Aluno.ordem, Aluno.id).all()
        idx = next((i for i, a in enumerate(alunos) if a.id == aluno_id), None)
        if idx is None:
            abort(404)
        alvo = idx - 1 if direcao == "cima" else idx + 1
        if 0 <= alvo < len(alunos):
            alunos[idx], alunos[alvo] = alunos[alvo], alunos[idx]
            for i, a in enumerate(alunos, start=1):
                a.ordem = i
            db.session.commit()
        return redirect(url_for("alunos_list", _anchor=f"a{aluno_id}"))

    @app.route("/alunos/exportar.xlsx")
    def alunos_exportar():
        buf = exportar_xlsx(lista_atual())
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"inscritos_{date.today():%Y-%m-%d}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.route("/modelo.xlsx")
    def modelo_planilha():
        exemplo = [{
            "inscricao": "-",
            "nome": "Nome Completo da Criança",
            "nascimento": "15/05/2024",
            "situacao": "LISTA DE ESPERA",
            "data_inscricao": date.today().strftime("%d/%m/%Y"),
            "observacao": "",
        }]
        return send_file(
            exportar_xlsx(exemplo, "Modelo"),
            as_attachment=True,
            download_name="modelo_inscritos.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ------------------------------------------------------------------ importação
    @app.route("/importar", methods=["GET", "POST"])
    def importar():
        cfg = Configuracao.atual()
        if request.method == "POST":
            arquivo = request.files.get("arquivo")
            if not arquivo or not arquivo.filename:
                flash("Selecione o arquivo da planilha.", "error")
                return redirect(url_for("importar"))
            try:
                registros, avisos = importar_arquivo(arquivo.filename, arquivo.read(), cfg.data_corte)
            except PlanilhaInvalida as exc:
                flash(str(exc), "error")
                return redirect(url_for("importar"))
            pendente = {"arquivo": arquivo.filename, "registros": registros, "avisos": avisos}
            with open(caminho_importacao_pendente(app), "w", encoding="utf-8") as f:
                json.dump(pendente, f, ensure_ascii=False)
            return redirect(url_for("importar_revisar"))
        return render_template("importar.html", cabecalhos=[CABECALHOS[c] for c in CAMPOS])

    @app.route("/importar/revisar")
    def importar_revisar():
        caminho = caminho_importacao_pendente(app)
        if not os.path.exists(caminho):
            return redirect(url_for("importar"))
        with open(caminho, encoding="utf-8") as f:
            pendente = json.load(f)
        diff = comparar(lista_atual(), pendente["registros"])
        return render_template("importar_revisar.html", pendente=pendente, diff=diff)

    @app.route("/importar/confirmar", methods=["POST"])
    def importar_confirmar():
        caminho = caminho_importacao_pendente(app)
        if not os.path.exists(caminho):
            flash("Nenhuma importação pendente.", "error")
            return redirect(url_for("importar"))
        with open(caminho, encoding="utf-8") as f:
            pendente = json.load(f)
        Aluno.query.delete()
        for i, reg in enumerate(pendente["registros"], start=1):
            db.session.add(Aluno(ordem=i, **reg))
        cfg = Configuracao.atual()
        cfg.ultimo_arquivo = pendente["arquivo"]
        cfg.ultima_importacao = datetime.now()
        db.session.commit()
        os.remove(caminho)
        flash(
            f"Lista atualizada com {len(pendente['registros'])} alunos de '{pendente['arquivo']}'. "
            "Confira e clique em 'Gerar HTML' para publicar e registrar no log.",
            "success",
        )
        return redirect(url_for("gerar"))

    @app.route("/importar/cancelar", methods=["POST"])
    def importar_cancelar():
        caminho = caminho_importacao_pendente(app)
        if os.path.exists(caminho):
            os.remove(caminho)
        flash("Importação descartada. A lista atual não foi alterada.", "success")
        return redirect(url_for("index"))

    # ------------------------------------------------------------------ configurações
    @app.route("/configuracoes", methods=["GET", "POST"])
    def configuracoes():
        cfg = Configuracao.atual()
        if request.method == "POST":
            erros = []
            try:
                data_corte = datetime.strptime(request.form.get("data_corte", ""), "%Y-%m-%d").date()
            except ValueError:
                data_corte = None
                erros.append("Data de corte inválida.")
            link_apto = request.form.get("link_apto", "").strip()
            link_menor = request.form.get("link_menor", "").strip()
            for rotulo, link in (("apto", link_apto), ("menor de 18 meses", link_menor)):
                if not RE_LINK.match(link):
                    erros.append(f"Link do formulário ({rotulo}) inválido: deve começar com https:// e não ter espaços ou aspas.")
            nome = limpar(request.form.get("nome_creche"))
            if not nome:
                erros.append("Informe o nome da creche.")
            if erros:
                for e in erros:
                    flash(e, "error")
                return render_template("config.html", form=request.form)
            cfg.data_corte = data_corte
            cfg.link_apto = link_apto
            cfg.link_menor = link_menor
            cfg.nome_creche = nome
            cfg.responsavel_padrao = limpar(request.form.get("responsavel_padrao"))
            db.session.commit()
            flash("Configurações salvas. Gere o HTML para que entrem na página publicada.", "success")
            return redirect(url_for("index"))
        return render_template("config.html", form=None)

    # ------------------------------------------------------------------ geração + log
    @app.route("/gerar", methods=["GET", "POST"])
    def gerar():
        cfg = Configuracao.atual()
        ultima, diff = pendencias(cfg)
        alunos = lista_atual()
        if request.method == "POST":
            responsavel = limpar(request.form.get("responsavel"))
            try:
                atualizado_em = datetime.strptime(request.form.get("atualizado_em", ""), "%Y-%m-%d").date()
            except ValueError:
                atualizado_em = None
            erros = []
            if not responsavel:
                erros.append("Informe o responsável pela atualização (fica registrado no log).")
            if atualizado_em is None:
                erros.append("Informe a data de atualização.")
            if not alunos:
                erros.append("A lista está vazia. Importe a planilha antes de gerar.")
            if erros:
                for e in erros:
                    flash(e, "error")
                return redirect(url_for("gerar"))

            html = gerar_html(alunos, cfg.data_corte, atualizado_em, cfg.nome_creche, cfg.link_apto, cfg.link_menor)
            reg = Atualizacao(
                gerado_em=datetime.now().replace(microsecond=0),
                atualizado_em=atualizado_em,
                data_corte=cfg.data_corte,
                nome_creche=cfg.nome_creche,
                link_apto=cfg.link_apto,
                link_menor=cfg.link_menor,
                responsavel=responsavel,
                motivo=request.form.get("motivo", "").strip(),
                arquivo_origem=cfg.ultimo_arquivo,
                total_alunos=len(alunos),
                novos_json=json.dumps(diff["novos"], ensure_ascii=False),
                removidos_json=json.dumps(diff["removidos"], ensure_ascii=False),
                alterados_json=json.dumps(diff["alterados"], ensure_ascii=False),
                parametros_json=json.dumps(diff["parametros"], ensure_ascii=False),
                snapshot_json=json.dumps(alunos, ensure_ascii=False),
                html=html,
                hash_html=sha256(html),
                hash_anterior=ultima.hash_cadeia if ultima else "",
            )
            reg.hash_cadeia = calcular_hash_cadeia(reg)
            db.session.add(reg)
            if not cfg.responsavel_padrao:
                cfg.responsavel_padrao = responsavel
            db.session.commit()
            flash(f"HTML gerado e registrado no log (atualização nº {reg.id}).", "success")
            return redirect(url_for("historico_detalhe", log_id=reg.id))
        return render_template("gerar.html", ultima=ultima, diff=diff, total=len(alunos), hoje=date.today())

    @app.route("/previa")
    def previa():
        cfg = Configuracao.atual()
        html = gerar_html(lista_atual(), cfg.data_corte, date.today(), cfg.nome_creche, cfg.link_apto, cfg.link_menor)
        return Response(documento_completo(html, "Prévia (não registrada)"), mimetype="text/html")

    # ------------------------------------------------------------------ histórico
    @app.route("/historico")
    def historico():
        registros = Atualizacao.query.order_by(Atualizacao.id).all()
        problemas = verificar_cadeia(registros)
        return render_template("historico.html", registros=list(reversed(registros)), problemas=problemas)

    @app.route("/historico/<int:log_id>")
    def historico_detalhe(log_id):
        reg = db.session.get(Atualizacao, log_id) or abort(404)
        return render_template("historico_detalhe.html", reg=reg)

    @app.route("/historico/<int:log_id>/pagina.html")
    def historico_download(log_id):
        reg = db.session.get(Atualizacao, log_id) or abort(404)
        return Response(
            reg.html,
            mimetype="text/html; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=inscricao_{reg.gerado_em:%Y-%m-%d_%H%M}_n{reg.id}.html"},
        )

    @app.route("/historico/<int:log_id>/visualizar")
    def historico_visualizar(log_id):
        reg = db.session.get(Atualizacao, log_id) or abort(404)
        return Response(documento_completo(reg.html, f"Atualização nº {reg.id}"), mimetype="text/html")

    @app.route("/historico/<int:log_id>/lista.xlsx")
    def historico_lista(log_id):
        reg = db.session.get(Atualizacao, log_id) or abort(404)
        return send_file(
            exportar_xlsx(reg.snapshot, f"Atualizacao {reg.id}"),
            as_attachment=True,
            download_name=f"lista_atualizacao_n{reg.id}_{reg.gerado_em:%Y-%m-%d}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.route("/historico/relatorio")
    def historico_relatorio():
        ini = request.args.get("de", "")
        fim = request.args.get("ate", "")
        consulta = Atualizacao.query
        try:
            if ini:
                consulta = consulta.filter(Atualizacao.gerado_em >= datetime.strptime(ini, "%Y-%m-%d"))
            if fim:
                limite = datetime.strptime(fim, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                consulta = consulta.filter(Atualizacao.gerado_em <= limite)
        except ValueError:
            abort(400)
        todos = Atualizacao.query.order_by(Atualizacao.id).all()
        return render_template(
            "historico_relatorio.html",
            registros=consulta.order_by(Atualizacao.id).all(),
            problemas=verificar_cadeia(todos),
            de_br="/".join(reversed(ini.split("-"))) if ini else "",
            ate_br="/".join(reversed(fim.split("-"))) if fim else "",
            emitido_em=datetime.now(),
        )

    @app.route("/historico/exportar.csv")
    def historico_csv():
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow([
            "Nº", "Gerado em", "Data 'Atualizado dia'", "Data de corte", "Responsável", "Motivo",
            "Arquivo de origem", "Total de alunos", "Novos", "Removidos", "Alterados",
            "Novos (nomes)", "Removidos (nomes)", "Hash do HTML (SHA-256)", "Hash da cadeia",
        ])
        for r in Atualizacao.query.order_by(Atualizacao.id).all():
            w.writerow([
                r.id, r.gerado_em.strftime("%d/%m/%Y %H:%M:%S"), r.atualizado_em.strftime("%d/%m/%Y"),
                r.data_corte.strftime("%d/%m/%Y"), r.responsavel, r.motivo, r.arquivo_origem or "",
                r.total_alunos, len(r.novos), len(r.removidos), len(r.alterados),
                ", ".join(a["nome"] for a in r.novos), ", ".join(a["nome"] for a in r.removidos),
                r.hash_html, r.hash_cadeia,
            ])
        return Response(
            "﻿" + buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=log_atualizacoes_{date.today():%Y-%m-%d}.csv"},
        )


def documento_completo(fragmento, titulo):
    """Envolve o fragmento do IPM num documento para visualização local (o fragmento em si não muda)."""
    return (
        f'<!doctype html><html lang="pt-br"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{titulo}</title>'
        f"</head><body style=\"margin:16px\">{fragmento}</body></html>"
    )


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
