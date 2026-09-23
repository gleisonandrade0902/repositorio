"""Geração do HTML publicado no IPM e cadeia de integridade do log de atualizações."""

import hashlib
import html
import json
from html.entities import codepoint2name

from flask import render_template
from markupsafe import Markup

from planilha import classe_status, cor_status, mascarar_nascimento

MODELO_IPM = "ipm/pagina_inscricao.html"


def entidades(texto):
    """Escapa como o editor do IPM salva: acentos viram entidades nomeadas (&ccedil;, &atilde;...)."""
    saida = []
    for ch in html.escape(str(texto or ""), quote=False):
        cp = ord(ch)
        if cp < 128:
            saida.append(ch)
        elif cp in codepoint2name:
            saida.append(f"&{codepoint2name[cp]};")
        else:
            saida.append(f"&#{cp};")
    return Markup("".join(saida))


def registrar_filtros(app):
    app.add_template_filter(entidades, "entidades")
    app.add_template_filter(mascarar_nascimento, "mascarar_nascimento")
    app.add_template_filter(classe_status, "classe_status")
    app.add_template_filter(cor_status, "cor_status")


def gerar_html(alunos, data_corte, atualizado_em, nome_creche, link_apto, link_menor):
    """Renderiza a página exatamente no formato do HTML oficial."""
    return render_template(
        MODELO_IPM,
        alunos=alunos,
        ano=data_corte.year,
        corte=data_corte,
        corte_br=data_corte.strftime("%d/%m/%Y"),
        atualizado_em=atualizado_em.strftime("%d/%m/%Y"),
        nome_creche=nome_creche,
        link_apto=link_apto,
        link_menor=link_menor,
    )


def sha256(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def calcular_hash_cadeia(reg):
    """Hash do registro inteiro + hash do registro anterior (encadeamento tipo 'livro-razão')."""
    conteudo = json.dumps(
        {
            "anterior": reg.hash_anterior,
            "gerado_em": reg.gerado_em.isoformat(timespec="seconds"),
            "atualizado_em": reg.atualizado_em.isoformat(),
            "data_corte": reg.data_corte.isoformat(),
            "nome_creche": reg.nome_creche,
            "link_apto": reg.link_apto,
            "link_menor": reg.link_menor,
            "responsavel": reg.responsavel,
            "motivo": reg.motivo,
            "arquivo_origem": reg.arquivo_origem or "",
            "snapshot": reg.snapshot_json,
            "html": reg.hash_html,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return sha256(conteudo)


def verificar_cadeia(registros):
    """Recebe os registros em ordem crescente de id. Retorna {id: [problemas]} (vazio = íntegro)."""
    problemas = {}
    anterior = ""
    for reg in registros:
        erros = []
        if reg.hash_anterior != anterior:
            erros.append("elo com o registro anterior não confere (registro removido ou alterado)")
        if sha256(reg.html) != reg.hash_html:
            erros.append("o HTML armazenado foi alterado após a geração")
        if calcular_hash_cadeia(reg) != reg.hash_cadeia:
            erros.append("os dados do registro foram alterados após a geração")
        if erros:
            problemas[reg.id] = erros
        anterior = reg.hash_cadeia
    return problemas
