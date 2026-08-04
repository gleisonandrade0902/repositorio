#!/usr/bin/env python3
"""
Gerador de Diário Oficial Eletrônico.

Junta vários PDFs (decretos, portarias, extratos, avisos, etc.) em um único
arquivo, aplicando em cada página o cabeçalho padrão do Diário Oficial
(brasão, título, edição, data) e o rodapé com numeração de página — no
mesmo modelo do PDF de referência (Diário Oficial Eletrônico de Carmópolis
de Minas - MG).

Uso:
    python gerar_diario.py                 -> abre a interface gráfica
    python gerar_diario.py --gui            -> idem
    python gerar_diario.py --cli            -> roda em modo texto (terminal),
                                                usando config.json
    python gerar_diario.py --config caminho/config.json --cli
"""

import argparse
import json
import os
import shutil
import sys
from datetime import date

import fitz  # PyMuPDF

# Quando rodando como executável (PyInstaller), os arquivos que o usuário edita
# (config.json, entrada/, saida/, ativos/) ficam ao lado do executável, não na
# pasta temporária onde o PyInstaller descompacta o programa.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    RECURSOS_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    RECURSOS_DIR = BASE_DIR

CONFIG_PATH_PADRAO = os.path.join(BASE_DIR, "config.json")


def preparar_pasta_trabalho():
    """No primeiro uso do executável, copia os arquivos padrão (config, ativos,
    pastas entrada/saida) para junto do executável, para que fiquem editáveis."""
    os.makedirs(os.path.join(BASE_DIR, "entrada"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "saida"), exist_ok=True)

    origem_ativos = os.path.join(RECURSOS_DIR, "ativos")
    destino_ativos = os.path.join(BASE_DIR, "ativos")
    if os.path.isdir(origem_ativos) and not os.path.isdir(destino_ativos):
        shutil.copytree(origem_ativos, destino_ativos)

    origem_config = os.path.join(RECURSOS_DIR, "config.json")
    if not os.path.isfile(CONFIG_PATH_PADRAO) and os.path.isfile(origem_config):
        shutil.copy2(origem_config, CONFIG_PATH_PADRAO)

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho",
    7: "julho", 8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

# Medidas em pontos (1/72"), página Letter (612 x 792), no mesmo layout do modelo.
PAGINA_LARGURA = 612
PAGINA_ALTURA = 792
MARGEM_ESQ = 70.9
MARGEM_DIR = 602.7
COR_LINHA = (49 / 255, 132 / 255, 155 / 255)  # teal do modelo
LOGO_RECT = fitz.Rect(37.5, 14.4, 133.0, 101.25)
LINHA_TOPO_Y = (100.5, 103.35)
LINHA_RODAPE_Y = (729.5, 732.4)
CONTEUDO_TOPO_Y = 112
CONTEUDO_BASE_Y = 745
NUM_PAGINA_PONTO = (555.0, 764.5)


def config_padrao():
    return {
        "municipio": "Nome do Município",
        "uf": "UF",
        "ano_diario": "I",
        "numero_edicao": 1,
        "data_edicao": "",
        "lei_numero": "",
        "lei_data": "",
        "site": "",
        "logo": "ativos/brasao_exemplo.png",
        "pasta_entrada": "entrada",
        "pasta_saida": "saida",
    }


def carregar_config(caminho):
    cfg = config_padrao()
    if os.path.isfile(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def salvar_config(caminho, cfg):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _resolver_caminho(cfg_dir, caminho):
    if not caminho:
        return None
    if os.path.isabs(caminho):
        return caminho
    return os.path.join(cfg_dir, caminho)


def _data_por_extenso(data_str):
    if data_str:
        try:
            dia, mes, ano = (int(p) for p in data_str.split("/"))
            d = date(ano, mes, dia)
        except (ValueError, TypeError):
            raise ValueError(f"Data inválida em 'data_edicao': {data_str!r}. Use o formato DD/MM/AAAA.")
    else:
        d = date.today()
    return d, f"{d.day:02d} de {MESES_PT[d.month].upper()} de {d.year}"


def _listar_pdfs_entrada(pasta_entrada):
    if not os.path.isdir(pasta_entrada):
        raise FileNotFoundError(f"Pasta de entrada não encontrada: {pasta_entrada}")
    arquivos = [
        f for f in os.listdir(pasta_entrada)
        if f.lower().endswith(".pdf")
    ]
    arquivos.sort(key=str.lower)
    if not arquivos:
        raise ValueError(
            f"Nenhum PDF encontrado em '{pasta_entrada}'. Coloque os PDFs a serem "
            f"publicados nessa pasta (dica: prefixe os nomes com 01_, 02_, 03_... "
            f"para controlar a ordem de publicação)."
        )
    return [os.path.join(pasta_entrada, f) for f in arquivos]


def _texto_edicao(cfg, data_extenso):
    partes = [f"{cfg['municipio']}-{cfg['uf']} {data_extenso}", "Diário Oficial Eletrônico"]
    ano_diario = (cfg.get("ano_diario") or "").strip()
    if ano_diario:
        partes.append(f"ANO {ano_diario}")
    numero_edicao = cfg.get("numero_edicao")
    if numero_edicao not in (None, ""):
        partes.append(f"Nº {numero_edicao}")
    linha = " - ".join(partes)
    if cfg.get("lei_numero"):
        linha += f" Lei {cfg['lei_numero']}"
        if cfg.get("lei_data"):
            linha += f" de {cfg['lei_data']}."
        else:
            linha += "."
    return linha


def _desenhar_cabecalho(pagina, cfg, texto_edicao, logo_caminho):
    if logo_caminho and os.path.isfile(logo_caminho):
        pagina.insert_image(LOGO_RECT, filename=logo_caminho, keep_proportion=True)

    titulo_x = LOGO_RECT.x1 + 20
    pagina.insert_text(
        fitz.Point(titulo_x, 38),
        "Diário Oficial Eletrônico",
        fontsize=24, fontname="hebo", color=(0, 0, 0),
    )
    pagina.insert_text(
        fitz.Point(titulo_x, 62),
        f"Município de {cfg['municipio']} - {cfg['uf']}",
        fontsize=14, fontname="helv", color=(0, 0, 0),
    )
    pagina.insert_textbox(
        fitz.Rect(titulo_x, 68, MARGEM_DIR, 100),
        texto_edicao,
        fontsize=8.5, fontname="helv", color=(0, 0, 0), align=0,
    )

    pagina.draw_line(
        fitz.Point(MARGEM_ESQ, sum(LINHA_TOPO_Y) / 2),
        fitz.Point(MARGEM_DIR, sum(LINHA_TOPO_Y) / 2),
        color=COR_LINHA, width=LINHA_TOPO_Y[1] - LINHA_TOPO_Y[0],
    )


def _desenhar_rodape(pagina, numero_pagina, ultima_pagina, cfg):
    if ultima_pagina:
        pagina.draw_line(
            fitz.Point(MARGEM_ESQ, sum(LINHA_RODAPE_Y) / 2),
            fitz.Point(MARGEM_DIR, sum(LINHA_RODAPE_Y) / 2),
            color=COR_LINHA, width=LINHA_RODAPE_Y[1] - LINHA_RODAPE_Y[0],
        )
        if cfg.get("site"):
            largura_texto = fitz.get_text_length(cfg["site"], fontname="hebo", fontsize=8)
            centro_x = (MARGEM_ESQ + MARGEM_DIR) / 2
            pagina.insert_text(
                fitz.Point(centro_x - largura_texto / 2, LINHA_RODAPE_Y[1] + 15),
                cfg["site"], fontsize=8, fontname="hebo", color=(0, 0, 1),
            )

    texto_pagina = str(numero_pagina)
    largura_pagina = fitz.get_text_length(texto_pagina, fontname="helv", fontsize=11)
    pagina.insert_text(
        fitz.Point(NUM_PAGINA_PONTO[0] - largura_pagina, NUM_PAGINA_PONTO[1]),
        texto_pagina, fontsize=11, fontname="helv", color=(0, 0, 0),
    )


def gerar_diario(cfg, cfg_dir=BASE_DIR, progresso=None):
    """Gera o PDF do Diário Oficial a partir da config e retorna o caminho do arquivo gerado."""
    for campo in ("municipio", "uf", "numero_edicao"):
        if not cfg.get(campo) and cfg.get(campo) != 0:
            raise ValueError(f"Preencha o campo obrigatório: {campo}")

    _, data_extenso = _data_por_extenso(cfg.get("data_edicao"))
    texto_edicao = _texto_edicao(cfg, data_extenso)

    pasta_entrada = _resolver_caminho(cfg_dir, cfg.get("pasta_entrada") or "entrada")
    pasta_saida = _resolver_caminho(cfg_dir, cfg.get("pasta_saida") or "saida")
    logo_caminho = _resolver_caminho(cfg_dir, cfg.get("logo"))
    os.makedirs(pasta_saida, exist_ok=True)

    arquivos_entrada = _listar_pdfs_entrada(pasta_entrada)

    saida = fitz.open()
    total_paginas = 0

    for caminho in arquivos_entrada:
        if progresso:
            progresso(f"Adicionando {os.path.basename(caminho)}...")
        origem = fitz.open(caminho)
        for pno in range(len(origem)):
            nova = saida.new_page(width=PAGINA_LARGURA, height=PAGINA_ALTURA)
            area_conteudo = fitz.Rect(MARGEM_ESQ, CONTEUDO_TOPO_Y, MARGEM_DIR, CONTEUDO_BASE_Y)
            nova.show_pdf_page(area_conteudo, origem, pno, keep_proportion=True)
            _desenhar_cabecalho(nova, cfg, texto_edicao, logo_caminho)
            total_paginas += 1
        origem.close()

    if total_paginas == 0:
        raise ValueError("Nenhuma página encontrada nos PDFs de entrada.")

    # Busca as páginas de novo pelo índice (em vez de reusar os objetos criados
    # acima) porque a referência Python de uma Page fica inválida assim que o
    # documento sofre outras operações depois dela ter sido criada.
    for i in range(total_paginas):
        pagina = saida[i]
        _desenhar_rodape(pagina, i + 1, ultima_pagina=(i + 1 == total_paginas), cfg=cfg)

    numero_edicao = cfg["numero_edicao"]
    nome_saida = f"Diario_Oficial_Edicao_{numero_edicao}.pdf"
    caminho_saida = os.path.join(pasta_saida, nome_saida)
    saida.save(caminho_saida)
    saida.close()

    if progresso:
        progresso(f"Concluído: {total_paginas} página(s) em {caminho_saida}")
    return caminho_saida


# ------------------------- CLI -------------------------

def rodar_cli(caminho_config):
    preparar_pasta_trabalho()
    cfg = carregar_config(caminho_config)
    cfg_dir = os.path.dirname(os.path.abspath(caminho_config))
    try:
        caminho_saida = gerar_diario(cfg, cfg_dir=cfg_dir, progresso=print)
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"\nDiário Oficial gerado com sucesso: {caminho_saida}")


# ------------------------- GUI -------------------------

def rodar_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    preparar_pasta_trabalho()
    cfg = carregar_config(CONFIG_PATH_PADRAO)

    janela = tk.Tk()
    janela.title("Gerador de Diário Oficial")
    janela.geometry("560x520")

    campos = {}

    def linha(label, chave, largura=40):
        frame = ttk.Frame(janela)
        frame.pack(fill="x", padx=12, pady=4)
        ttk.Label(frame, text=label, width=18).pack(side="left")
        var = tk.StringVar(value=str(cfg.get(chave, "")))
        entrada = ttk.Entry(frame, textvariable=var, width=largura)
        entrada.pack(side="left", fill="x", expand=True)
        campos[chave] = var
        return frame, var

    ttk.Label(janela, text="Gerador de Diário Oficial Eletrônico", font=("", 14, "bold")).pack(pady=10)

    linha("Município", "municipio")
    linha("UF", "uf", largura=6)
    linha("Ano do Diário (ex: XIII)", "ano_diario", largura=10)
    linha("Nº da Edição", "numero_edicao", largura=10)
    linha("Data da Edição (DD/MM/AAAA)", "data_edicao", largura=16)
    linha("Lei nº", "lei_numero", largura=16)
    linha("Data da Lei (DD/MM/AAAA)", "lei_data", largura=16)
    linha("Site", "site")

    def escolher_arquivo(var):
        caminho = filedialog.askopenfilename(
            title="Selecione o brasão/logo", filetypes=[("Imagens", "*.png *.jpg *.jpeg")]
        )
        if caminho:
            var.set(caminho)

    def escolher_pasta(var):
        caminho = filedialog.askdirectory(title="Selecione a pasta")
        if caminho:
            var.set(caminho)

    frame_logo = ttk.Frame(janela)
    frame_logo.pack(fill="x", padx=12, pady=4)
    ttk.Label(frame_logo, text="Logo/Brasão", width=18).pack(side="left")
    var_logo = tk.StringVar(value=str(cfg.get("logo", "")))
    ttk.Entry(frame_logo, textvariable=var_logo).pack(side="left", fill="x", expand=True)
    ttk.Button(frame_logo, text="...", width=3, command=lambda: escolher_arquivo(var_logo)).pack(side="left")
    campos["logo"] = var_logo

    frame_in = ttk.Frame(janela)
    frame_in.pack(fill="x", padx=12, pady=4)
    ttk.Label(frame_in, text="Pasta de entrada (PDFs)", width=18).pack(side="left")
    var_in = tk.StringVar(value=str(cfg.get("pasta_entrada", "entrada")))
    ttk.Entry(frame_in, textvariable=var_in).pack(side="left", fill="x", expand=True)
    ttk.Button(frame_in, text="...", width=3, command=lambda: escolher_pasta(var_in)).pack(side="left")
    campos["pasta_entrada"] = var_in

    frame_out = ttk.Frame(janela)
    frame_out.pack(fill="x", padx=12, pady=4)
    ttk.Label(frame_out, text="Pasta de saída", width=18).pack(side="left")
    var_out = tk.StringVar(value=str(cfg.get("pasta_saida", "saida")))
    ttk.Entry(frame_out, textvariable=var_out).pack(side="left", fill="x", expand=True)
    ttk.Button(frame_out, text="...", width=3, command=lambda: escolher_pasta(var_out)).pack(side="left")
    campos["pasta_saida"] = var_out

    status_var = tk.StringVar(value="Pronto.")
    ttk.Label(janela, textvariable=status_var, foreground="#31849B").pack(pady=6)

    def coletar_config():
        nova_cfg = dict(cfg)
        for chave, var in campos.items():
            nova_cfg[chave] = var.get().strip()
        if nova_cfg.get("numero_edicao"):
            try:
                nova_cfg["numero_edicao"] = int(nova_cfg["numero_edicao"])
            except ValueError:
                pass
        return nova_cfg

    def gerar():
        nova_cfg = coletar_config()
        salvar_config(CONFIG_PATH_PADRAO, nova_cfg)
        status_var.set("Gerando...")
        janela.update_idletasks()
        try:
            caminho_saida = gerar_diario(nova_cfg, cfg_dir=BASE_DIR, progresso=status_var.set)
        except Exception as exc:
            status_var.set("Erro.")
            messagebox.showerror("Erro ao gerar o Diário", str(exc))
            return
        status_var.set(f"Concluído: {caminho_saida}")
        messagebox.showinfo("Diário Oficial gerado", f"Arquivo gerado com sucesso:\n\n{caminho_saida}")

    ttk.Button(janela, text="Gerar Diário Oficial", command=gerar).pack(pady=10, ipadx=10, ipady=6)

    janela.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Gerador de Diário Oficial Eletrônico (junta PDFs com cabeçalho padrão).")
    parser.add_argument("--gui", action="store_true", help="Abre a interface gráfica (padrão quando nenhum outro modo é informado).")
    parser.add_argument("--cli", action="store_true", help="Executa em modo texto, sem interface gráfica.")
    parser.add_argument("--config", default=CONFIG_PATH_PADRAO, help="Caminho do arquivo config.json (usado no modo --cli).")
    args = parser.parse_args()

    if args.cli:
        rodar_cli(args.config)
    else:
        try:
            rodar_gui()
        except ImportError:
            print(
                "Aviso: interface gráfica (tkinter) indisponível neste ambiente. "
                "Executando em modo texto (--cli) com config.json.",
                file=sys.stderr,
            )
            rodar_cli(args.config)


if __name__ == "__main__":
    main()
