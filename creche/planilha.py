"""Leitura das planilhas de inscritos (.xls, .xlsx, .csv), normalização e comparação."""

import csv
import io
import re
import unicodedata
from datetime import date, datetime, timedelta

import openpyxl
import xlrd

CAMPOS = ("inscricao", "nome", "nascimento", "situacao", "data_inscricao", "observacao")

CABECALHOS = {
    "inscricao": "Inscrição",
    "nome": "Nome do Candidato",
    "nascimento": "Nascimento",
    "situacao": "Situação",
    "data_inscricao": "Data Inscrição",
    "observacao": "Observação",
}

SITUACAO_SEM_VALOR = "EM ANÁLISE"
EXTENSOES = ("xls", "xlsx", "xlsm", "csv")


class PlanilhaInvalida(ValueError):
    pass


# --------------------------------------------------------------------------- texto

def normalizar(texto):
    """Minúsculas, sem acentos e sem pontuação — usado para comparar e casar cabeçalhos."""
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def limpar(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\s+", " ", str(valor)).strip()


def identificar_coluna(cabecalho):
    h = normalizar(cabecalho)
    if not h or re.search(r"\b(mae|pai|responsavel|responsaveis)\b", h):
        return None
    if "nasc" in h or h == "dn":
        return "nascimento"
    if "obs" in h or "detalhe" in h or "justific" in h:
        return "observacao"
    if "situa" in h or "status" in h:
        return "situacao"
    if "carimbo" in h or ("data" in h and "insc" in h) or h in ("data", "inscrito em", "timestamp"):
        return "data_inscricao"
    if "insc" in h or "protocolo" in h or h in ("n", "no", "numero"):
        return "inscricao"
    if "nome" in h or "candidato" in h or "aluno" in h or "crianca" in h:
        return "nome"
    return None


# --------------------------------------------------------------------------- datas

_RE_DMA = re.compile(r"^(\*\*|\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4}|\d{2})\b")
_RE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")
_RE_MA = re.compile(r"^(\d{1,2})[/.\-](\d{4})$")


def formatar_data(valor, permitir_mascara=False):
    """Converte o valor da célula para 'DD/MM/AAAA' (ou '**/MM/AAAA').

    Retorna (texto, ok). Quando não reconhece, devolve o texto original e ok=False.
    """
    if valor is None or valor == "":
        return "", False
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y"), True
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y"), True
    if isinstance(valor, (int, float)) and 20000 < valor < 80000:
        # número serial do Excel (célula de data sem formatação)
        return (datetime(1899, 12, 30) + timedelta(days=float(valor))).strftime("%d/%m/%Y"), True

    texto = limpar(valor)
    dia = mes = ano = None
    m = _RE_DMA.match(texto)
    if m:
        dia, mes, ano = m.group(1), int(m.group(2)), int(m.group(3))
        if ano < 100:
            ano += 2000
    elif (m := _RE_ISO.match(texto)):
        ano, mes, dia = int(m.group(1)), int(m.group(2)), m.group(3)
    elif permitir_mascara and (m := _RE_MA.match(texto)):
        dia, mes, ano = "**", int(m.group(1)), int(m.group(2))
    else:
        return texto, False

    if dia == "**":
        if not permitir_mascara or not 1 <= mes <= 12:
            return texto, False
        return f"**/{mes:02d}/{ano}", True
    try:
        return date(ano, mes, int(dia)).strftime("%d/%m/%Y"), True
    except ValueError:
        return texto, False


def data_de_texto(texto):
    """'DD/MM/AAAA' -> date; None se mascarado ou inválido."""
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def mascarar_nascimento(texto):
    texto = texto or ""
    if re.match(r"^\d{2}/\d{2}/\d{4}$", texto):
        return "**" + texto[2:]
    return texto


def idade_em_meses(nascimento, referencia):
    """Mesma conta do botão 'Calcular idade' da página publicada."""
    meses = (referencia.year - nascimento.year) * 12 + (referencia.month - nascimento.month)
    if referencia.day < nascimento.day:
        meses -= 1
    return meses


# --------------------------------------------------------------------------- leitura

def _linhas_xlsx(conteudo):
    wb = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    try:
        return [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()


def _linhas_xls(conteudo):
    livro = xlrd.open_workbook(file_contents=conteudo)
    folha = livro.sheet_by_index(0)
    linhas = []
    for r in range(folha.nrows):
        linha = []
        for c in range(folha.ncols):
            celula = folha.cell(r, c)
            if celula.ctype == xlrd.XL_CELL_DATE:
                linha.append(xlrd.xldate_as_datetime(celula.value, livro.datemode))
            else:
                linha.append(celula.value)
        linhas.append(linha)
    return linhas


def _linhas_csv(conteudo):
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("latin-1")
    try:
        dialeto = csv.Sniffer().sniff(texto[:4096], delimiters=";,\t")
    except csv.Error:
        dialeto = csv.excel
    return [list(r) for r in csv.reader(io.StringIO(texto), dialeto)]


def ler_linhas(nome_arquivo, conteudo):
    ext = nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else ""
    if ext not in EXTENSOES:
        raise PlanilhaInvalida("Formato não suportado. Envie um arquivo .xls, .xlsx ou .csv.")
    try:
        if ext == "csv":
            return _linhas_csv(conteudo)
        # arquivos .xlsx renomeados para .xls (e vice-versa) são comuns
        if conteudo[:2] == b"PK":
            return _linhas_xlsx(conteudo)
        return _linhas_xls(conteudo)
    except PlanilhaInvalida:
        raise
    except Exception as exc:  # arquivo corrompido, protegido por senha, HTML disfarçado de .xls...
        raise PlanilhaInvalida(f"Não foi possível ler a planilha: {exc}") from exc


def interpretar(linhas, data_corte=None):
    """Transforma as linhas cruas em registros. Retorna (registros, avisos)."""
    avisos = []
    cabecalho_idx, mapa = None, {}
    for i, linha in enumerate(linhas[:15]):
        tentativa = {}
        for col, valor in enumerate(linha):
            campo = identificar_coluna(valor)
            if campo and campo not in tentativa:
                tentativa[campo] = col
        if "nome" in tentativa:
            cabecalho_idx, mapa = i, tentativa
            break
    if cabecalho_idx is None:
        raise PlanilhaInvalida(
            "Não encontrei a linha de cabeçalho. A planilha precisa ter ao menos a coluna "
            "'Nome do Candidato' (ou 'Nome', 'Aluno', 'Criança')."
        )
    for campo in ("nascimento", "situacao", "data_inscricao"):
        if campo not in mapa:
            avisos.append(f"Coluna '{CABECALHOS[campo]}' não encontrada — o campo ficará vazio.")

    registros, vistos = [], {}
    for n, linha in enumerate(linhas[cabecalho_idx + 1:], start=cabecalho_idx + 2):
        def celula(campo):
            col = mapa.get(campo)
            return linha[col] if col is not None and col < len(linha) else None

        nome = limpar(celula("nome"))
        if not nome:
            continue
        reg = {
            "inscricao": limpar(celula("inscricao")) or "-",
            "nome": nome,
            "situacao": limpar(celula("situacao")).upper(),
            "observacao": limpar(celula("observacao")),
        }
        reg["nascimento"], ok_nasc = formatar_data(celula("nascimento"), permitir_mascara=True)
        reg["data_inscricao"], ok_insc = formatar_data(celula("data_inscricao"))

        if "nascimento" in mapa and not ok_nasc:
            avisos.append(f"Linha {n} ({nome}): data de nascimento não reconhecida: '{reg['nascimento']}'.")
        if "data_inscricao" in mapa and not ok_insc:
            avisos.append(f"Linha {n} ({nome}): data de inscrição não reconhecida: '{reg['data_inscricao']}'.")
        if not reg["situacao"]:
            reg["situacao"] = SITUACAO_SEM_VALOR
            if "situacao" in mapa:
                avisos.append(f"Linha {n} ({nome}): sem situação — marcado como '{SITUACAO_SEM_VALOR}'.")

        nasc = data_de_texto(reg["nascimento"])
        if nasc and data_corte:
            meses = idade_em_meses(nasc, data_corte)
            if meses < 0:
                avisos.append(f"Linha {n} ({nome}): nascimento posterior à data de corte.")
            elif meses >= 48 and classe_status(reg["situacao"]) == "status-ok":
                avisos.append(
                    f"Linha {n} ({nome}): terá {meses // 12} anos na data de corte, "
                    f"mas está como '{reg['situacao']}'."
                )

        k = chave(reg)
        if k in vistos:
            avisos.append(f"Linha {n} ({nome}): possível duplicidade com a linha {vistos[k]}.")
        vistos.setdefault(k, n)
        registros.append(reg)

    if not registros:
        raise PlanilhaInvalida("A planilha não contém nenhum aluno (coluna de nome vazia).")
    return registros, avisos


def importar_arquivo(nome_arquivo, conteudo, data_corte=None):
    return interpretar(ler_linhas(nome_arquivo, conteudo), data_corte)


# --------------------------------------------------------------------------- status

STATUS_OK = ("LISTA DE ESPERA", "MATRICULAD", "APTO", "CLASSIFICAD", "APROVAD")


def classe_status(situacao):
    s = normalizar(situacao).upper()
    return "status-ok" if s.startswith(tuple(normalizar(x).upper() for x in STATUS_OK)) else "status-nok"


def cor_status(situacao):
    return "#27ae60" if classe_status(situacao) == "status-ok" else "#dc3545"


# --------------------------------------------------------------------------- comparação

def chave(reg):
    return f"{normalizar(reg['nome'])}|{mascarar_nascimento(reg.get('nascimento', ''))}"


ROTULOS = {c: CABECALHOS[c] for c in CAMPOS}


def comparar(anterior, atual):
    """Diferenças entre duas listas: novos, removidos e alterados (por nome + mês/ano de nascimento)."""
    antes = {chave(r): r for r in anterior}
    depois = {chave(r): r for r in atual}
    novos = [r for k, r in depois.items() if k not in antes]
    removidos = [r for k, r in antes.items() if k not in depois]
    alterados = []
    for k, r in depois.items():
        if k not in antes:
            continue
        mudancas = [
            {"campo": ROTULOS[c], "de": antes[k].get(c, ""), "para": r.get(c, "")}
            for c in ("inscricao", "nome", "nascimento", "situacao", "data_inscricao", "observacao")
            if (antes[k].get(c) or "") != (r.get(c) or "")
        ]
        if mudancas:
            alterados.append({"nome": r["nome"], "nascimento": r["nascimento"], "mudancas": mudancas})
    return {"novos": novos, "removidos": removidos, "alterados": alterados}


# --------------------------------------------------------------------------- exportação

def exportar_xlsx(registros, titulo="Inscritos"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = titulo[:31]
    ws.append([CABECALHOS[c] for c in CAMPOS])
    for r in registros:
        ws.append([r.get(c, "") for c in CAMPOS])
    for col, largura in zip("ABCDEF", (12, 42, 14, 40, 16, 60)):
        ws.column_dimensions[col].width = largura
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
