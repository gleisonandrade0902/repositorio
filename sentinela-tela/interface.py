"""
Painel gráfico (Tkinter) do Sentinela de Tela — Modo Pro.

Abas: Painel · Pessoas · Tentativas de acesso · Configurações
Tkinter vem com o Python e usa ~20 MB, mantendo o total < 300 MB.
Imagens são convertidas via PNG em memória (sem depender de Pillow).
"""
import base64
import logging
import queue
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import cv2

import banco as bd
import config
import sistema
from config import BASE, PASTA_CAPTURAS
from nucleo import Coletor, abrir_camera

log = logging.getLogger("sentinela.gui")

# Paleta (tema escuro)
COR = {
    "fundo": "#12161c", "painel": "#1b2129", "borda": "#2a323d", "texto": "#e6e9ee",
    "suave": "#8b95a5", "destaque": "#3d8bfd", "ok": "#2fbf71", "alerta": "#f0a020",
    "perigo": "#e5484d", "campo": "#232a34",
}
COR_MODO = {
    "monitorando": COR["ok"], "vigiando tela de bloqueio": COR["alerta"],
    "bloqueado": COR["alerta"], "pausado": COR["suave"], "erro": COR["perigo"],
    "sem pessoas cadastradas": COR["alerta"], "câmera em uso pelo cadastro": COR["destaque"],
}


def data_br(iso):
    """'2026-11-26 13:53:53' -> '26/11/2026 13:53:53'"""
    d, _, h = iso.partition(" ")
    a, m, dia = d.split("-")
    return f"{dia}/{m}/{a} {h}"


def cv_para_tk(img, max_w, max_h):
    """ndarray BGR -> tk.PhotoImage redimensionada mantendo proporção."""
    h, w = img.shape[:2]
    esc = min(max_w / w, max_h / h, 1.0)
    if esc < 1.0:
        img = cv2.resize(img, (int(w * esc), int(h * esc)), interpolation=cv2.INTER_AREA)
    ok, png = cv2.imencode(".png", img)
    return tk.PhotoImage(data=base64.b64encode(png.tobytes()))


# ==========================================================================
class App(tk.Tk):
    def __init__(self, cfg, banco, motor, minimizado=False):
        super().__init__()
        self.cfg, self.banco, self.motor = cfg, banco, motor
        self.fila_ui = queue.Queue()  # comandos vindos da bandeja / outra instância
        self.title("Sentinela de Tela — Pro")
        self.geometry("980x640")
        self.minsize(860, 560)
        self.configure(bg=COR["fundo"])
        self._estilo()
        self.bandeja = Bandeja(self)

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=10, pady=10)
        self.aba_painel = AbaPainel(self)
        self.aba_pessoas = AbaPessoas(self)
        self.aba_tentativas = AbaTentativas(self)
        self.aba_config = AbaConfig(self)
        self.abas.add(self.aba_painel, text="  Painel  ")
        self.abas.add(self.aba_pessoas, text="  Pessoas  ")
        self.abas.add(self.aba_tentativas, text="  Tentativas de acesso  ")
        self.abas.add(self.aba_config, text="  Configurações  ")
        self.abas.bind("<<NotebookTabChanged>>", self._ao_trocar_aba)
        self.aba_tentativas.atualizar()

        self.protocol("WM_DELETE_WINDOW", self.fechar_janela)
        if minimizado:
            self.fechar_janela()
        self.after(250, self._laco)

    # ---------------- estilo ----------------
    def _estilo(self):
        fonte = ("Segoe UI", 10) if sistema.SO == "Windows" else ("DejaVu Sans", 10)
        self.fonte, self.fonte_b = fonte, (fonte[0], fonte[1], "bold")
        self.option_add("*Dialog.msg.font", fonte)
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=COR["fundo"], foreground=COR["texto"],
                    fieldbackground=COR["campo"], bordercolor=COR["borda"],
                    lightcolor=COR["borda"], darkcolor=COR["borda"], font=fonte)
        s.configure("TNotebook", background=COR["fundo"], borderwidth=0)
        s.configure("TNotebook.Tab", background=COR["painel"], foreground=COR["suave"],
                    padding=(12, 6), borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", COR["destaque"])],
              foreground=[("selected", "#ffffff")])
        s.configure("TFrame", background=COR["fundo"])
        s.configure("Card.TFrame", background=COR["painel"])
        s.configure("TLabel", background=COR["fundo"], foreground=COR["texto"])
        s.configure("Card.TLabel", background=COR["painel"])
        s.configure("Suave.TLabel", background=COR["painel"], foreground=COR["suave"])
        s.configure("Titulo.TLabel", background=COR["fundo"], font=(fonte[0], 13, "bold"))
        s.configure("TLabelframe", background=COR["painel"], bordercolor=COR["borda"])
        s.configure("TLabelframe.Label", background=COR["painel"], foreground=COR["destaque"],
                    font=self.fonte_b)
        s.configure("TCheckbutton", background=COR["painel"], foreground=COR["texto"])
        s.map("TCheckbutton", background=[("active", COR["painel"])])
        s.configure("TButton", background=COR["campo"], foreground=COR["texto"],
                    padding=(10, 5), borderwidth=1)
        s.map("TButton", background=[("active", COR["borda"]), ("disabled", COR["painel"])],
              foreground=[("disabled", COR["suave"])])
        s.configure("Primario.TButton", background=COR["destaque"], foreground="#fff")
        s.map("Primario.TButton", background=[("active", "#2f6fd0")])
        s.configure("Perigo.TButton", background=COR["perigo"], foreground="#fff")
        s.map("Perigo.TButton", background=[("active", "#b8383c")])
        s.configure("Treeview", background=COR["painel"], fieldbackground=COR["painel"],
                    foreground=COR["texto"], rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading", background=COR["campo"], foreground=COR["suave"],
                    relief="flat", font=self.fonte_b)
        s.map("Treeview", background=[("selected", COR["destaque"])])
        s.configure("TSpinbox", arrowcolor=COR["texto"], foreground=COR["texto"])
        s.configure("TEntry", foreground=COR["texto"], insertcolor=COR["texto"])
        s.configure("TCombobox", foreground=COR["texto"], arrowcolor=COR["texto"],
                    background=COR["campo"])
        s.map("TCombobox", fieldbackground=[("readonly", COR["campo"])],
              foreground=[("readonly", COR["texto"])],
              selectbackground=[("readonly", COR["campo"])],
              selectforeground=[("readonly", COR["texto"])])
        self.option_add("*TCombobox*Listbox.background", COR["campo"])
        self.option_add("*TCombobox*Listbox.foreground", COR["texto"])
        self.option_add("*TCombobox*Listbox.selectBackground", COR["destaque"])
        s.configure("Vertical.TScrollbar", background=COR["campo"], troughcolor=COR["painel"],
                    arrowcolor=COR["texto"], bordercolor=COR["painel"])
        s.configure("Horizontal.TProgressbar", background=COR["ok"], troughcolor=COR["campo"])

    # ---------------- PIN ----------------
    def pedir_pin(self, motivo="continuar"):
        if not config.tem_pin(self.cfg):
            return True
        pin = DialogoPin(self, motivo).resultado
        if pin is None:
            return False
        if config.conferir_pin(self.cfg, pin):
            return True
        self.banco.registrar(bd.SISTEMA, f"PIN incorreto ao tentar {motivo}", visto=True)
        messagebox.showerror("PIN incorreto", "PIN incorreto.")
        return False

    # ---------------- janela ----------------
    def mostrar(self):
        if self.state() in ("withdrawn", "iconic") and config.tem_pin(self.cfg):
            if not self.pedir_pin("abrir o painel"):
                return
        self.deiconify()
        self.lift()
        self.focus_force()

    def fechar_janela(self):
        # No Linux nem todo ambiente tem bandeja: minimiza para não "sumir" a janela
        if self.bandeja.ativa and sistema.SO in ("Windows", "Darwin"):
            self.withdraw()
        else:
            self.iconify()

    def sair(self):
        if not self.pedir_pin("encerrar o Sentinela"):
            return
        if not messagebox.askyesno("Encerrar", "Encerrar o Sentinela? O computador "
                                   "deixará de ser protegido.", parent=self):
            return
        self.bandeja.parar()
        self.motor.parar()
        self.destroy()

    def alternar_pausa(self):
        if not self.motor.pausado and not self.pedir_pin("pausar a proteção"):
            return
        self.motor.pausar(not self.motor.pausado)

    def _ao_trocar_aba(self, _e=None):
        aba = self.abas.nametowidget(self.abas.select())
        if hasattr(aba, "atualizar"):
            aba.atualizar()

    # ---------------- laço da interface ----------------
    def _laco(self):
        try:
            self._passo()
        except tk.TclError:
            return  # janela destruída
        except Exception:
            log.exception("Erro no laço da interface")
        self.after(250, self._laco)

    def _passo(self):
        try:
            while True:
                cmd = self.fila_ui.get_nowait()
                {"mostrar": self.mostrar, "pausar": self.alternar_pausa,
                 "bloquear": self.motor.bloquear_agora, "sair": self.sair}.get(cmd, lambda: None)()
        except queue.Empty:
            pass
        try:
            while True:
                tipo, dado = self.motor.eventos.get_nowait()
                if tipo == "novo_evento":
                    self.aba_tentativas.atualizar()
                    self.aba_painel.atualizar_eventos()
                elif tipo == "alerta":
                    JanelaAlerta(self, dado)
                elif tipo == "bloqueio" and config.tem_pin(self.cfg) and self.bandeja.ativa:
                    self.withdraw()  # ao bloquear, o painel só reabre com PIN
        except queue.Empty:
            pass
        self.aba_painel.atualizar_status()
        self.bandeja.atualizar()


# ==========================================================================
class DialogoPin(tk.Toplevel):
    """Pede o PIN numa janela independente (funciona com o painel escondido)."""

    def __init__(self, app, motivo):
        super().__init__(app)
        self.resultado = None
        self.title("PIN do painel")
        self.configure(bg=COR["painel"], padx=18, pady=14)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        ttk.Label(self, text=f"Digite o PIN para {motivo}:", style="Card.TLabel").pack(anchor="w")
        self.ent = ttk.Entry(self, show="•", width=22)
        self.ent.pack(fill="x", pady=8)
        b = ttk.Frame(self, style="Card.TFrame")
        b.pack(fill="x")
        ttk.Button(b, text="OK", style="Primario.TButton", command=self._ok).pack(side="right")
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(50, self._foco)
        self.wait_window(self)

    def _foco(self):
        self.lift()
        self.ent.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _ok(self):
        self.resultado = self.ent.get()
        self.destroy()


class AbaPainel(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.abas, padding=14)
        self.app = app
        self._foto = None

        topo = ttk.Frame(self, style="Card.TFrame", padding=16)
        topo.pack(fill="x")
        self.lbl_ponto = tk.Label(topo, text="●", font=(app.fonte[0], 28), bg=COR["painel"],
                                  fg=COR["suave"])
        self.lbl_ponto.pack(side="left", padx=(0, 12))
        caixa = ttk.Frame(topo, style="Card.TFrame")
        caixa.pack(side="left", fill="x", expand=True)
        self.lbl_modo = ttk.Label(caixa, text="Iniciando…", style="Card.TLabel",
                                  font=(app.fonte[0], 16, "bold"))
        self.lbl_modo.pack(anchor="w")
        self.lbl_detalhe = ttk.Label(caixa, text="", style="Suave.TLabel")
        self.lbl_detalhe.pack(anchor="w")
        botoes = ttk.Frame(topo, style="Card.TFrame")
        botoes.pack(side="right")
        self.bt_pausa = ttk.Button(botoes, text="Pausar", command=app.alternar_pausa)
        self.bt_pausa.pack(side="left", padx=4)
        ttk.Button(botoes, text="Bloquear agora", style="Perigo.TButton",
                   command=app.motor.bloquear_agora).pack(side="left", padx=4)
        ttk.Button(botoes, text="Encerrar", command=app.sair).pack(side="left", padx=4)

        # Indicadores
        ind = ttk.Frame(self)
        ind.pack(fill="x", pady=12)
        self.ind = {}
        for i, (k, t) in enumerate([("frente", "Diante da tela"), ("tela", "Tela"),
                                    ("pessoas", "Pessoas cadastradas"), ("hoje", "Tentativas hoje"),
                                    ("ram", "Memória")]):
            c = ttk.Frame(ind, style="Card.TFrame", padding=(12, 8))
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            ind.columnconfigure(i, weight=1)
            ttk.Label(c, text=t, style="Suave.TLabel").pack(anchor="w")
            v = ttk.Label(c, text="—", style="Card.TLabel", font=(app.fonte[0], 13, "bold"))
            v.pack(anchor="w")
            self.ind[k] = v

        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)
        # Câmera
        cam = ttk.LabelFrame(corpo, text="Câmera ao vivo", padding=10)
        cam.pack(side="left", fill="y")
        self.var_preview = tk.BooleanVar(value=False)
        ttk.Checkbutton(cam, text="Mostrar imagem (usa um pouco mais de CPU)",
                        variable=self.var_preview, command=self._preview).pack(anchor="w")
        self.lbl_cam = tk.Label(cam, bg="#000", width=320, height=240, fg=COR["suave"],
                                text="Pré-visualização desligada")
        self.lbl_cam.pack(pady=(8, 0))
        # Eventos recentes
        ev = ttk.LabelFrame(corpo, text="Atividade recente", padding=10)
        ev.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.tv = ttk.Treeview(ev, columns=("data", "tipo", "desc"), show="headings", height=9)
        for c, t, w in (("data", "Data/hora", 150), ("tipo", "Evento", 200), ("desc", "Detalhe", 180)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, minwidth=80, anchor="w", stretch=(c == "desc"))
        self.tv.tag_configure("tentativa", foreground=COR["alerta"])
        self.tv.pack(fill="both", expand=True)
        self.atualizar_eventos()

    def _preview(self):
        self.app.motor.preview_ativo = self.var_preview.get()
        if not self.var_preview.get():
            self.app.motor.frame_preview = None
            self._foto = None
            self.lbl_cam.configure(image="", text="Pré-visualização desligada")

    def atualizar_eventos(self):
        self.tv.delete(*self.tv.get_children())
        for r in self.app.banco.listar_eventos(limite=30):
            tag = ("tentativa",) if r["tipo"] in bd.TIPOS_TENTATIVA else ()
            self.tv.insert("", "end", values=(data_br(r["data_hora"]), bd.ROTULOS.get(r["tipo"], r["tipo"]),
                                              r["descricao"] or ""), tags=tag)

    def atualizar_status(self):
        m = self.app.motor
        st = m.status
        modo = st["modo"]
        self.lbl_ponto.configure(fg=COR_MODO.get(modo, COR["suave"]))
        self.lbl_modo.configure(text=modo.capitalize())
        det = st["erro"] or ("Proteção ativa." if modo == "monitorando" else "")
        if st["economia"]:
            det += f"  Modo econômico de memória nível {st['economia']}."
        self.lbl_detalhe.configure(text=det)
        self.bt_pausa.configure(text="Retomar" if m.pausado else "Pausar")
        frente = st["presentes"]
        self.ind["frente"].configure(text=", ".join(frente) if frente else "ninguém")
        self.ind["tela"].configure(text="ligada" if st["tela_ligada"] else "desligada")
        self.ind["pessoas"].configure(text=str(m.visao.total_pessoas))
        self.ind["ram"].configure(text=f"{st['ram']:.0f} / {self.app.cfg['limite_memoria_mb']} MB")
        if not hasattr(self, "_cont_hoje") or self._cont_hoje <= 0:
            self.ind["hoje"].configure(text=str(self.app.banco.contar_tentativas_hoje()))
            if self.winfo_ismapped():
                self.atualizar_eventos()
            self._cont_hoje = 20  # recalcula a cada ~5 s
        self._cont_hoje -= 1
        if self.var_preview.get() and m.frame_preview is not None and self.winfo_ismapped():
            self._foto = cv_para_tk(m.frame_preview, 320, 240)
            self.lbl_cam.configure(image=self._foto, text="", width=320, height=240)


# ==========================================================================
class AbaPessoas(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.abas, padding=14)
        self.app = app
        ttk.Label(self, text="Pessoas autorizadas", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self, text="Quem estiver nesta lista pode usar o computador. Nenhuma foto é "
                  "guardada: apenas assinaturas numéricas do rosto.",
                  foreground=COR["suave"]).pack(anchor="w", pady=(0, 10))
        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Button(barra, text="+ Adicionar pessoa", style="Primario.TButton",
                   command=self.adicionar).pack(side="left")
        for txt, fn in (("Recadastrar rosto", self.recadastrar), ("Renomear", self.renomear),
                        ("Ativar / desativar", self.alternar)):
            ttk.Button(barra, text=txt, command=fn).pack(side="left", padx=(8, 0))
        ttk.Button(barra, text="Excluir", style="Perigo.TButton",
                   command=self.excluir).pack(side="right")

        self.tv = ttk.Treeview(self, columns=("nome", "amostras", "cadastro", "situacao"),
                               show="headings", selectmode="browse")
        for c, t, w in (("nome", "Nome", 300), ("amostras", "Amostras", 100),
                        ("cadastro", "Cadastrado em", 180), ("situacao", "Situação", 120)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor="w")
        self.tv.tag_configure("inativo", foreground=COR["suave"])
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", lambda e: self.renomear())
        self.atualizar()

    def atualizar(self):
        self.tv.delete(*self.tv.get_children())
        for p in self.app.banco.listar_pessoas():
            self.tv.insert("", "end", iid=str(p["id"]), tags=() if p["ativo"] else ("inativo",),
                           values=(p["nome"], p["amostras"], data_br(p["criado_em"]),
                                   "ativa" if p["ativo"] else "desativada"))

    def _selecionada(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Pessoas", "Selecione uma pessoa na lista.", parent=self)
            return None
        return int(sel[0])

    def _alterou(self):
        self.app.motor.recarregar_pessoas()
        self.atualizar()

    def adicionar(self):
        if not self.app.pedir_pin("cadastrar uma pessoa"):
            return
        nome = simpledialog.askstring("Nova pessoa", "Nome da pessoa:", parent=self)
        if nome and nome.strip():
            DialogoCadastro(self.app, nome.strip(), None, self._alterou)

    def recadastrar(self):
        pid = self._selecionada()
        if pid and self.app.pedir_pin("recadastrar"):
            nome = self.tv.item(str(pid))["values"][0]
            DialogoCadastro(self.app, nome, pid, self._alterou)

    def renomear(self):
        pid = self._selecionada()
        if not pid:
            return
        atual = self.tv.item(str(pid))["values"][0]
        nome = simpledialog.askstring("Renomear", "Novo nome:", initialvalue=atual, parent=self)
        if nome and nome.strip():
            self.app.banco.renomear_pessoa(pid, nome.strip())
            self._alterou()

    def alternar(self):
        pid = self._selecionada()
        if pid and self.app.pedir_pin("alterar a situação"):
            ativo = self.tv.item(str(pid))["values"][3] == "ativa"
            self.app.banco.ativar_pessoa(pid, not ativo)
            self._alterou()

    def excluir(self):
        pid = self._selecionada()
        if not pid or not self.app.pedir_pin("excluir"):
            return
        nome = self.tv.item(str(pid))["values"][0]
        if messagebox.askyesno("Excluir", f"Excluir '{nome}' e sua assinatura facial?", parent=self):
            self.app.banco.excluir_pessoa(pid)
            self._alterou()


class DialogoCadastro(tk.Toplevel):
    """Captura ao vivo das amostras do rosto, com barra de progresso."""

    def __init__(self, app, nome, pessoa_id, ao_concluir):
        super().__init__(app)
        self.app, self.nome, self.pid, self.ao_concluir = app, nome, pessoa_id, ao_concluir
        self.title(f"Cadastro facial — {nome}")
        self.configure(bg=COR["painel"], padx=16, pady=16)
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self.cam = None
        self._foto = None
        ttk.Label(self, text=f"Cadastrando: {nome}", style="Card.TLabel",
                  font=app.fonte_b).pack(anchor="w")
        ttk.Label(self, text="Fique sozinho(a), com boa luz, olhando para a câmera. "
                  "Mova levemente a cabeça.", style="Suave.TLabel").pack(anchor="w", pady=(2, 10))
        self.lbl = tk.Label(self, bg="#000", width=480, height=360, fg=COR["suave"],
                            text="Abrindo câmera…")
        self.lbl.pack()
        self.barra = ttk.Progressbar(self, length=480, maximum=1.0)
        self.barra.pack(pady=(10, 4))
        self.msg = ttk.Label(self, text="", style="Card.TLabel")
        self.msg.pack(anchor="w")
        ttk.Button(self, text="Cancelar", command=self.fechar).pack(anchor="e", pady=(10, 0))
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.coletor = Coletor(app.motor.visao, app.cfg["amostras_cadastro"])
        self.after(50, self._abrir)

    def _abrir(self):
        if not self.app.motor.emprestar_camera():
            messagebox.showerror("Câmera", "O monitor não liberou a câmera.", parent=self)
            return self.fechar()
        try:
            self.cam = abrir_camera(self.app.cfg["camera_indice"])
        except RuntimeError as e:
            messagebox.showerror("Câmera", str(e), parent=self)
            return self.fechar()
        self._quadro()

    def _quadro(self):
        if self.cam is None:
            return
        ok, frame = self.cam.read()
        if ok:
            msg, faces, escala = self.coletor.processar(frame)
            cor = (60, 200, 60) if len(faces) == 1 else (40, 40, 230)
            for f in faces:
                x, y, w, h = (int(v / escala) for v in f[:4])
                cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)
            self._foto = cv_para_tk(frame, 480, 360)
            self.lbl.configure(image=self._foto, text="")
            self.barra["value"] = self.coletor.progresso
            self.msg.configure(text=f"{msg}  ({len(self.coletor.amostras)}/{self.coletor.alvo})")
            if self.coletor.concluido:
                return self._salvar()
        self.after(60, self._quadro)

    def _salvar(self):
        emb = self.coletor.resultado()
        if self.pid:
            self.app.banco.atualizar_assinaturas(self.pid, emb)
        else:
            self.app.banco.adicionar_pessoa(self.nome, emb)
        self.app.banco.registrar(bd.SISTEMA, f"Rosto cadastrado: {self.nome}", visto=True)
        self.fechar()
        self.ao_concluir()
        messagebox.showinfo("Cadastro", f"{self.nome} cadastrado(a) com sucesso!", parent=self.app)

    def fechar(self):
        if self.cam is not None:
            self.cam.release()
            self.cam = None
        self.app.motor.devolver_camera()
        self.grab_release()
        self.destroy()


# ==========================================================================
class AbaTentativas(ttk.Frame):
    FILTROS = {
        "Todas as tentativas": bd.TIPOS_TENTATIVA,
        bd.ROTULOS[bd.SENHA_INCORRETA]: (bd.SENHA_INCORRETA,),
        bd.ROTULOS[bd.INTRUSO_BLOQUEIO]: (bd.INTRUSO_BLOQUEIO,),
        bd.ROTULOS[bd.INTRUSO_SESSAO]: (bd.INTRUSO_SESSAO,),
        "Histórico completo": None,
    }

    def __init__(self, app):
        super().__init__(app.abas, padding=14)
        self.app = app
        self._foto = None
        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Tentativas de acesso", style="Titulo.TLabel").pack(side="left")
        self.var_filtro = tk.StringVar(value="Todas as tentativas")
        cb = ttk.Combobox(barra, textvariable=self.var_filtro, values=list(self.FILTROS),
                          state="readonly", width=38)
        cb.pack(side="right")
        cb.bind("<<ComboboxSelected>>", lambda e: self.atualizar())

        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)
        dir_ = ttk.Frame(corpo, style="Card.TFrame", padding=10)
        dir_.pack(side="right", fill="y", padx=(12, 0))  # empacota antes: largura garantida
        esq = ttk.Frame(corpo)
        esq.pack(side="left", fill="both", expand=True)
        self.tv = ttk.Treeview(esq, columns=("data", "tipo", "desc"), show="headings")
        for c, t, w in (("data", "Data/hora", 150), ("tipo", "Tipo", 180), ("desc", "Detalhe", 160)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, minwidth=80, anchor="w", stretch=(c == "desc"))
        self.tv.tag_configure("novo", foreground=COR["alerta"], font=app.fonte_b)
        sb = ttk.Scrollbar(esq, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tv.bind("<<TreeviewSelect>>", self._selecionar)

        self.lbl_foto = tk.Label(dir_, bg="#000", width=400, height=300, fg=COR["suave"],
                                 text="Selecione uma tentativa")
        self.lbl_foto.pack()
        self.lbl_info = ttk.Label(dir_, text="", style="Card.TLabel", wraplength=400, justify="left")
        self.lbl_info.pack(anchor="w", pady=8)
        g = ttk.Frame(dir_, style="Card.TFrame")
        g.pack(fill="x")
        ttk.Button(g, text="Abrir foto", command=self.abrir_foto).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(g, text="Salvar cópia…", command=self.exportar).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(g, text="Abrir pasta", command=lambda: sistema.abrir_pasta(PASTA_CAPTURAS)
                   ).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(g, text="Marcar todas como vistas", command=self.marcar_vistas
                   ).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(g, text="Excluir", style="Perigo.TButton", command=self.excluir
                   ).grid(row=2, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(g, text="Excluir todas", style="Perigo.TButton", command=self.excluir_todas
                   ).grid(row=2, column=1, sticky="ew", padx=2, pady=2)
        g.columnconfigure((0, 1), weight=1)
        self._linhas = {}
        self.atualizar()

    def atualizar(self):
        sel = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        self._linhas = {}
        for r in self.app.banco.listar_eventos(self.FILTROS[self.var_filtro.get()]):
            self._linhas[str(r["id"])] = r
            self.tv.insert("", "end", iid=str(r["id"]), tags=("novo",) if not r["visto"] else (),
                           values=(data_br(r["data_hora"]), bd.ROTULOS.get(r["tipo"], r["tipo"]),
                                   r["descricao"] or ""))
        manter = [i for i in sel if self.tv.exists(i)]
        if manter:
            self.tv.selection_set(manter)
        n = len(self.app.banco.nao_vistas())
        if str(self) not in self.app.abas.tabs():
            return  # ainda não adicionada ao Notebook
        self.app.abas.tab(self, text=f"  Tentativas de acesso ({n})  " if n else
                          "  Tentativas de acesso  ")

    def _atual(self):
        sel = self.tv.selection()
        return self._linhas.get(sel[0]) if sel else None

    def _selecionar(self, _e=None):
        r = self._atual()
        if not r:
            return
        if not r["visto"]:
            self.app.banco.marcar_vistos([r["id"]])
            self.tv.item(str(r["id"]), tags=())
        info = f"{data_br(r['data_hora'])}\n{bd.ROTULOS.get(r['tipo'], r['tipo'])}\n{r['descricao'] or ''}"
        if r["similaridade"] is not None:
            info += f"\nMaior semelhança com cadastrados: {r['similaridade']:.2f}"
        self.lbl_info.configure(text=info)
        caminho = BASE / r["foto"] if r["foto"] else None
        img = cv2.imread(str(caminho)) if caminho and caminho.exists() else None
        if img is not None:
            self._foto = cv_para_tk(img, 400, 300)
            self.lbl_foto.configure(image=self._foto, text="")
        else:
            self._foto = None
            self.lbl_foto.configure(image="", text="Sem foto para este evento")

    def abrir_foto(self):
        r = self._atual()
        if r and r["foto"] and (BASE / r["foto"]).exists():
            sistema.abrir_pasta(BASE / r["foto"])

    def exportar(self):
        r = self._atual()
        if not (r and r["foto"]):
            return
        destino = filedialog.asksaveasfilename(parent=self, defaultextension=".jpg",
                                               initialfile=(BASE / r["foto"]).name,
                                               filetypes=[("Imagem JPEG", "*.jpg")])
        if destino:
            shutil.copy2(BASE / r["foto"], destino)

    def marcar_vistas(self):
        self.app.banco.marcar_vistos()
        self.atualizar()

    def excluir(self):
        r = self._atual()
        if r and self.app.pedir_pin("excluir o registro"):
            self.app.banco.excluir_eventos([r["id"]])
            self.atualizar()

    def excluir_todas(self):
        if not self._linhas or not self.app.pedir_pin("excluir registros"):
            return
        if messagebox.askyesno("Excluir", f"Excluir os {len(self._linhas)} registros desta lista "
                               "e suas fotos?", parent=self):
            self.app.banco.excluir_eventos([int(i) for i in self._linhas])
            self.atualizar()


class JanelaAlerta(tk.Toplevel):
    """Mostrada ao desbloquear quando houve tentativas enquanto você estava fora."""

    def __init__(self, app, eventos):
        super().__init__(app)
        self.app = app
        self.title("Sentinela — tentativas de acesso")
        self.configure(bg=COR["painel"], padx=18, pady=16)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        n = len(eventos)
        tk.Label(self, text=f"⚠  {n} tentativa(s) de acesso enquanto você estava fora",
                 bg=COR["painel"], fg=COR["alerta"], font=(app.fonte[0], 13, "bold")).pack(anchor="w")
        ultimo = eventos[0]
        tk.Label(self, text=f"Mais recente: {data_br(ultimo['data_hora'])} — {ultimo['descricao']}",
                 bg=COR["painel"], fg=COR["texto"]).pack(anchor="w", pady=(4, 10))
        self._foto = None
        com_foto = next((e for e in eventos if e["foto"] and (BASE / e["foto"]).exists()), None)
        if com_foto:
            img = cv2.imread(str(BASE / com_foto["foto"]))
            if img is not None:
                self._foto = cv_para_tk(img, 480, 360)
                tk.Label(self, image=self._foto, bg="#000").pack()
        b = ttk.Frame(self, style="Card.TFrame")
        b.pack(fill="x", pady=(12, 0))
        ttk.Button(b, text="Ver todas", style="Primario.TButton", command=self._ver).pack(side="right")
        ttk.Button(b, text="Fechar", command=self.destroy).pack(side="right", padx=8)
        self.bell()

    def _ver(self):
        self.destroy()
        self.app.mostrar()
        self.app.abas.select(self.app.aba_tentativas)
        self.app.aba_tentativas.atualizar()


# ==========================================================================
class AbaConfig(ttk.Frame):
    # (grupo, chave, rótulo, tipo, mín, máx, passo)
    CAMPOS = [
        ("Tempos", "segundos_para_desligar_tela", "Desligar a tela após (segundos sem ninguém)", int, 2, 600, 1),
        ("Tempos", "minutos_para_bloquear", "Bloquear após (minutos de ausência)", int, 1, 240, 1),
        ("Reconhecimento", "limiar_reconhecimento", "Rigor do reconhecimento (0.30 – 0.70)", float, 0.30, 0.70, 0.01),
        ("Reconhecimento", "exigir_olhar_para_tela", "Exigir que a pessoa esteja olhando para a tela", bool),
        ("Reconhecimento", "yaw_max", "Tolerância de cabeça virada (0.15 – 0.60)", float, 0.15, 0.60, 0.01),
        ("Reconhecimento", "amostras_cadastro", "Amostras por cadastro", int, 10, 60, 1),
        ("Segurança", "bloquear_se_estranho", "Bloquear quando aparecer pessoa não cadastrada", bool),
        ("Segurança", "bloquear_estranho_mesmo_com_dono", "Bloquear mesmo se a pessoa autorizada estiver junto", bool),
        ("Segurança", "verificacoes_para_estranho", "Confirmações antes de agir (≈3 por segundo)", int, 1, 30, 1),
        ("Segurança", "vigiar_durante_bloqueio", "Vigiar a tela de bloqueio (câmera continua ligada)", bool),
        ("Segurança", "capturar_fotos", "Fotografar tentativas de acesso", bool),
        ("Segurança", "intervalo_entre_capturas_s", "Intervalo mínimo entre fotos (segundos)", int, 5, 3600, 5),
        ("Segurança", "dias_retencao_fotos", "Apagar registros após (dias; 0 = nunca)", int, 0, 3650, 1),
        ("Segurança", "alerta_ao_desbloquear", "Avisar ao desbloquear se houve tentativas", bool),
        ("Sistema", "camera_indice", "Índice da câmera (0 = padrão)", int, 0, 9, 1),
        ("Sistema", "fps_verificacao", "Análises por segundo", int, 1, 10, 1),
        ("Sistema", "fps_durante_bloqueio", "Análises por segundo na tela de bloqueio", int, 1, 5, 1),
        ("Sistema", "limite_memoria_mb", "Limite de memória (MB)", int, 150, 2000, 10),
        ("Sistema", "iniciar_com_sistema", "Iniciar automaticamente ao entrar no computador", bool),
    ]

    def __init__(self, app):
        super().__init__(app.abas)
        self.app = app
        # Área rolável
        canvas = tk.Canvas(self, bg=COR["fundo"], highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.interno = ttk.Frame(canvas, padding=14)
        self.interno.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        jan = canvas.create_window((0, 0), window=self.interno, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(jan, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
                        if self.winfo_ismapped() else None)

        self.vars = {}
        grupos, linhas = {}, {}
        for campo in self.CAMPOS:
            g, chave, rotulo, tipo = campo[:4]
            if g not in grupos:
                grupos[g] = ttk.LabelFrame(self.interno, text=g, padding=12)
                grupos[g].pack(fill="x", pady=(0, 10))
                grupos[g].columnconfigure(0, weight=1)
            fr = grupos[g]
            lin = linhas[g] = linhas.get(g, -1) + 1
            if tipo is bool:
                v = tk.BooleanVar()
                ttk.Checkbutton(fr, text=rotulo, variable=v).grid(row=lin, column=0, columnspan=2,
                                                                  sticky="w", pady=3)
            else:
                v = tk.StringVar()
                ttk.Label(fr, text=rotulo, style="Card.TLabel").grid(row=lin, column=0, sticky="w", pady=3)
                mn, mx, passo = campo[4:]
                ttk.Spinbox(fr, from_=mn, to=mx, increment=passo, textvariable=v, width=10,
                            format="%.2f" if tipo is float else "%.0f").grid(row=lin, column=1, sticky="e")
            self.vars[chave] = (v, campo)

        # Senha incorreta (Windows)
        fs = ttk.LabelFrame(self.interno, text="Foto ao digitar senha incorreta", padding=12)
        fs.pack(fill="x", pady=(0, 10))
        self.lbl_fs = ttk.Label(fs, text="", style="Card.TLabel", wraplength=780, justify="left")
        self.lbl_fs.pack(anchor="w")
        ttk.Button(fs, text="Ativar (pede permissão de administrador)",
                   command=self._ativar_senha).pack(anchor="w", pady=(8, 0))

        # PIN
        fp = ttk.LabelFrame(self.interno, text="PIN do painel", padding=12)
        fp.pack(fill="x", pady=(0, 10))
        ttk.Label(fp, text="Protege abrir o painel, pausar, encerrar e alterar cadastros.",
                  style="Suave.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(fp, text="Novo PIN", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        self.pin1 = ttk.Entry(fp, show="•", width=14)
        self.pin1.grid(row=1, column=1, padx=6)
        ttk.Label(fp, text="Repetir", style="Card.TLabel").grid(row=1, column=2, sticky="w")
        self.pin2 = ttk.Entry(fp, show="•", width=14)
        self.pin2.grid(row=1, column=3, padx=6)
        ttk.Button(fp, text="Definir PIN", command=self._definir_pin).grid(row=1, column=4, padx=6)
        ttk.Button(fp, text="Remover PIN", command=self._remover_pin).grid(row=1, column=5)

        b = ttk.Frame(self.interno)
        b.pack(fill="x", pady=6)
        ttk.Button(b, text="Salvar configurações", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(b, text="Restaurar padrão", command=self.padrao).pack(side="right", padx=8)
        self.atualizar()

    def atualizar(self):
        for chave, (v, campo) in self.vars.items():
            val = self.app.cfg[chave]
            v.set(val if campo[3] is bool else (f"{val:.2f}" if campo[3] is float else str(int(val))))
        if sistema.SO != "Windows":
            txt = ("Disponível apenas no Windows. Nos demais sistemas, o Sentinela fotografa "
                   "qualquer rosto não cadastrado diante da tela de bloqueio.")
        elif self.app.motor.falha_senha_configurada:
            txt = "✔ Ativo: quem errar a senha na tela de bloqueio será fotografado."
        else:
            txt = ("Desativado. Sem isso, o Sentinela ainda fotografa rostos não cadastrados diante "
                   "da tela de bloqueio; com isso, a foto é tirada no instante da senha errada.")
        self.lbl_fs.configure(text=txt)

    def _ativar_senha(self):
        bat = BASE / "configurar_senha_incorreta.bat"
        if not sistema.executar_como_admin(bat):
            messagebox.showinfo("Senha incorreta", "Execute como administrador o arquivo:\n"
                                f"{bat}", parent=self)
        else:
            messagebox.showinfo("Senha incorreta", "Após concluir a janela do administrador, "
                                "reinicie o Sentinela para ativar.", parent=self)

    def _definir_pin(self):
        p1, p2 = self.pin1.get(), self.pin2.get()
        if len(p1) < 4 or not p1.isdigit():
            return messagebox.showerror("PIN", "Use pelo menos 4 dígitos.", parent=self)
        if p1 != p2:
            return messagebox.showerror("PIN", "Os PINs não conferem.", parent=self)
        if not self.app.pedir_pin("trocar o PIN"):
            return
        config.definir_pin(self.app.cfg, p1)
        config.salvar(self.app.cfg)
        self.pin1.delete(0, "end")
        self.pin2.delete(0, "end")
        messagebox.showinfo("PIN", "PIN definido.", parent=self)

    def _remover_pin(self):
        if config.tem_pin(self.app.cfg) and self.app.pedir_pin("remover o PIN"):
            config.definir_pin(self.app.cfg, "")
            config.salvar(self.app.cfg)
            messagebox.showinfo("PIN", "PIN removido.", parent=self)

    def salvar(self):
        if not self.app.pedir_pin("alterar configurações"):
            return
        novo = {}
        for chave, (v, campo) in self.vars.items():
            tipo = campo[3]
            if tipo is bool:
                novo[chave] = bool(v.get())
                continue
            try:
                val = tipo(float(v.get().replace(",", ".")))
            except ValueError:
                return messagebox.showerror("Configurações", f"Valor inválido em: {campo[2]}", parent=self)
            novo[chave] = min(max(val, campo[4]), campo[5])
        if novo["iniciar_com_sistema"] != self.app.cfg["iniciar_com_sistema"]:
            try:
                sistema.iniciar_com_sistema(novo["iniciar_com_sistema"], BASE / "app.py")
            except Exception as e:
                messagebox.showerror("Inicialização automática", str(e), parent=self)
                novo["iniciar_com_sistema"] = self.app.cfg["iniciar_com_sistema"]
        self.app.cfg.update(novo)
        config.salvar(self.app.cfg)
        self.app.motor.aplicar_config()
        self.atualizar()
        messagebox.showinfo("Configurações", "Configurações salvas e aplicadas.", parent=self)

    def padrao(self):
        for chave, (v, campo) in self.vars.items():
            val = config.PADRAO[chave]
            v.set(val if campo[3] is bool else (f"{val:.2f}" if campo[3] is float else str(int(val))))


# ==========================================================================
class Bandeja:
    """Ícone na bandeja do sistema (opcional: requer pystray + Pillow)."""

    def __init__(self, app):
        self.app = app
        self.ativa = False
        self.icone = None
        self._ultimo_estado = None
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception as e:  # ausente ou sem servidor gráfico compatível
            log.info("Bandeja indisponível (%s); fechar a janela irá minimizá-la", e)
            return
        self._Image, self._Draw, self._pystray = Image, ImageDraw, pystray
        fila = app.fila_ui
        menu = pystray.Menu(
            pystray.MenuItem("Abrir painel", lambda: fila.put("mostrar"), default=True),
            pystray.MenuItem(lambda i: "Retomar proteção" if app.motor.pausado else "Pausar proteção",
                             lambda: fila.put("pausar")),
            pystray.MenuItem("Bloquear agora", lambda: fila.put("bloquear")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Encerrar", lambda: fila.put("sair")),
        )
        try:
            self.icone = pystray.Icon("sentinela", self._imagem(COR["ok"]), "Sentinela de Tela", menu)
            self.icone.run_detached()
            self.ativa = True
        except Exception as e:
            log.info("Bandeja indisponível: %s", e)

    def _imagem(self, cor):
        img = self._Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = self._Draw.Draw(img)
        d.ellipse((4, 14, 60, 50), outline=cor, width=6)          # olho
        d.ellipse((22, 22, 42, 42), fill=cor)                      # pupila
        return img

    def atualizar(self):
        if not self.ativa:
            return
        modo = self.app.motor.status["modo"]
        if modo != self._ultimo_estado:
            self._ultimo_estado = modo
            try:
                self.icone.icon = self._imagem(COR_MODO.get(modo, COR["suave"]))
                self.icone.title = f"Sentinela de Tela - {modo}"
            except Exception as e:  # problema na bandeja nunca derruba o painel
                log.debug("Bandeja: %s", e)

    def parar(self):
        if self.icone is not None:
            try:
                self.icone.stop()
            except Exception:
                pass
