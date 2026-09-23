"""Testes do sistema de inscrições. Rodar a partir da pasta creche/:

    python -m unittest discover -s tests -v
"""

import io
import os
import sys
import tempfile
import unittest
from datetime import date, datetime

import openpyxl

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

from app import create_app  # noqa: E402
from models import Atualizacao, db  # noqa: E402
from planilha import comparar, formatar_data, importar_arquivo  # noqa: E402

LINK_APTO = "https://forms.gle/uZ9oi6YXtaJ81nEb9"
LINK_MENOR = "https://forms.gle/VkN9rkHUMxP1CqLdA"

ALUNOS = [
    ["-", "João Exemplo da Conceição", "12/03/2025", "F. I", "10/03/2026", ""],
    ["-", "Maria Fictícia Araújo", "**/08/2024", "lista de espera", "16/04/2026", ""],
    ["-", "Ana Teste", datetime(2024, 1, 5), "MATRICULADA", datetime(2026, 5, 14, 9, 30), ""],
    ["-", "Pedro Modelo", "01/03/2023", "MATRICULADO", "10/08/2026",
     "Matricula efetivada conforme os critérios estabelecidos para concessão de vaga, tendo prioridade no atendimento."],
]


def planilha_xlsx(linhas, cabecalho=("Inscrição", "Nome do Candidato", "Nascimento", "Situação", "Data Inscrição", "Observação")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(cabecalho))
    for linha in linhas:
        ws.append(linha)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class BaseApp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{os.path.join(self.tmp.name, 'teste.db')}",
            "TESTING": True,
        })
        self.app.instance_path = self.tmp.name
        self.c = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.tmp.cleanup()

    def configurar(self, corte="2026-03-31", apto=LINK_APTO, menor=LINK_MENOR):
        r = self.c.post("/configuracoes", data={
            "data_corte": corte, "link_apto": apto, "link_menor": menor,
            "nome_creche": "Creche Municipal Dona Léa", "responsavel_padrao": "",
        })
        self.assertEqual(r.status_code, 302)

    def importar(self, conteudo, nome="lista.xlsx"):
        r = self.c.post("/importar", data={"arquivo": (io.BytesIO(conteudo), nome)}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        self.assertIn("revisar", r.location)
        self.assertEqual(self.c.post("/importar/confirmar").status_code, 302)

    def gerar(self, dia="2026-09-17"):
        r = self.c.post("/gerar", data={"atualizado_em": dia, "responsavel": "Secretaria", "motivo": "teste"})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            return Atualizacao.query.order_by(Atualizacao.id.desc()).first().html


class TestHtmlIdentico(BaseApp):
    def test_html_igual_ao_modelo_oficial(self):
        with open(os.path.join(AQUI, "referencia_ipm.html"), encoding="utf-8") as f:
            referencia = f.read()
        self.configurar()
        self.importar(planilha_xlsx(ALUNOS))
        self.assertEqual(self.gerar(), referencia)

    def test_nova_data_de_corte_e_links_mudam_so_o_necessario(self):
        with open(os.path.join(AQUI, "referencia_ipm.html"), encoding="utf-8") as f:
            referencia = f.read()
        self.configurar(corte="2027-03-31", apto="https://forms.gle/NOVOapto", menor="https://forms.gle/NOVOmenor")
        self.importar(planilha_xlsx(ALUNOS))
        html = self.gerar(dia="2026-10-01")
        esperado = (
            referencia.replace("ESCOLAR 2026 (Atualizado dia 17/09/2026)", "ESCOLAR 2027 (Atualizado dia 01/10/2026)")
            .replace("31/03/2026", "31/03/2027")
            .replace("new Date(2026, 2, 31)", "new Date(2027, 2, 31)")
            .replace(LINK_APTO, "https://forms.gle/NOVOapto")
            .replace(LINK_MENOR, "https://forms.gle/NOVOmenor")
        )
        self.assertEqual(html, esperado)
        self.assertEqual(html.count("31/03/2027"), 5)

    def test_link_invalido_rejeitado(self):
        r = self.c.post("/configuracoes", data={
            "data_corte": "2027-03-31", "link_apto": "https://x.com/a');alert(1);//",
            "link_menor": LINK_MENOR, "nome_creche": "Creche",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("inválido".encode(), r.data)


class TestLog(BaseApp):
    def test_log_registra_novos_alterados_removidos(self):
        self.configurar()
        self.importar(planilha_xlsx(ALUNOS[:3]))
        self.gerar()
        nova = [list(a) for a in ALUNOS[1:]]
        nova[0][3] = "MATRICULADA"  # Maria saiu da lista de espera
        self.importar(planilha_xlsx(nova))
        self.gerar()
        with self.app.app_context():
            primeiro, segundo = Atualizacao.query.order_by(Atualizacao.id).all()
            self.assertEqual(len(primeiro.novos), 3)
            self.assertEqual([a["nome"] for a in segundo.novos], ["Pedro Modelo"])
            self.assertEqual([a["nome"] for a in segundo.removidos], ["João Exemplo da Conceição"])
            self.assertEqual(segundo.alterados[0]["mudancas"][0]["para"], "MATRICULADA")
            self.assertEqual(segundo.hash_anterior, primeiro.hash_cadeia)

    def test_integridade_detecta_adulteracao(self):
        self.configurar()
        self.importar(planilha_xlsx(ALUNOS))
        self.gerar()
        self.gerar()
        self.assertIn("íntegros".encode(), self.c.get("/historico").data)
        with self.app.app_context():
            reg = db.session.get(Atualizacao, 1)
            reg.responsavel = "Outra pessoa"
            db.session.commit()
        pagina = self.c.get("/historico").data
        self.assertIn("violado".encode(), pagina)
        self.assertIn("falhou em 1 registro".encode(), pagina)

    def test_paginas_abrem(self):
        self.configurar()
        self.importar(planilha_xlsx(ALUNOS))
        self.gerar()
        for url in ("/", "/alunos", "/alunos/novo", "/alunos/1/editar", "/importar", "/configuracoes", "/gerar",
                    "/previa", "/historico", "/historico/1", "/historico/1/visualizar", "/historico/1/pagina.html",
                    "/historico/1/lista.xlsx", "/historico/relatorio?de=2026-01-01&ate=2026-12-31",
                    "/historico/exportar.csv", "/alunos/exportar.xlsx", "/modelo.xlsx"):
            self.assertEqual(self.c.get(url).status_code, 200, url)

    def test_adicionar_aluno_manual(self):
        self.configurar()
        self.importar(planilha_xlsx(ALUNOS))
        r = self.c.post("/alunos/novo", data={"nome": "Lia Nova", "nascimento": "05/06/2024",
                                              "situacao": "lista de espera", "data_inscricao": "22/09/2026"})
        self.assertEqual(r.status_code, 302)
        html = self.gerar()
        self.assertIn("<td>Lia Nova</td>\n<td>**/06/2024</td>\n<td class=\"status-ok\">LISTA DE ESPERA</td>\n<td>22/09/2026</td>", html)


class TestPlanilha(unittest.TestCase):
    def test_datas(self):
        self.assertEqual(formatar_data("5/3/2024"), ("05/03/2024", True))
        self.assertEqual(formatar_data("2024-03-05"), ("05/03/2024", True))
        self.assertEqual(formatar_data("17/09/2026 10:22:01"), ("17/09/2026", True))
        self.assertEqual(formatar_data("**/12/2021", permitir_mascara=True), ("**/12/2021", True))
        self.assertEqual(formatar_data("12/2021", permitir_mascara=True), ("**/12/2021", True))
        self.assertEqual(formatar_data(45000), ("15/03/2023", True))
        self.assertFalse(formatar_data("31/02/2024")[1])

    def test_cabecalhos_variados_e_colunas_ignoradas(self):
        conteudo = planilha_xlsx(
            [["x", "Nome Mãe", "Lia", "01/02/2024", "123.456.789-00", "Lista de espera"]],
            cabecalho=("Carimbo de data/hora", "Nome da mãe", "Nome completo da criança", "Data de nascimento", "CPF", "Status"),
        )
        regs, avisos = importar_arquivo("f.xlsx", conteudo)
        self.assertEqual(regs[0]["nome"], "Lia")
        self.assertEqual(regs[0]["situacao"], "LISTA DE ESPERA")
        self.assertNotIn("123.456.789-00", str(regs))

    def test_avisos(self):
        conteudo = planilha_xlsx([
            ["-", "Ana", "10/01/2021", "LISTA DE ESPERA", "01/02/2026", ""],
            ["-", "ana", "10/01/2021", "", "xx", ""],
        ])
        _, avisos = importar_arquivo("f.xlsx", conteudo, date(2026, 3, 31))
        texto = " ".join(avisos)
        self.assertIn("5 anos", texto)
        self.assertIn("duplicidade", texto)
        self.assertIn("sem situação", texto)
        self.assertIn("não reconhecida", texto)

    def test_comparar(self):
        a = [{"nome": "Ana", "nascimento": "10/01/2024", "situacao": "LISTA DE ESPERA"}]
        b = [{"nome": "ANA ", "nascimento": "**/01/2024", "situacao": "MATRICULADA"}]
        d = comparar(a, b)
        self.assertEqual((len(d["novos"]), len(d["removidos"]), len(d["alterados"])), (0, 0, 1))


if __name__ == "__main__":
    unittest.main()
