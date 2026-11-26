"""
Controle de tela e sessão, multiplataforma (Windows / Linux X11 / macOS).

Cada função é "best effort": se a plataforma não suportar, registra no log
e segue sem derrubar o programa.
"""
import ctypes
import logging
import platform
import shutil
import subprocess
import time

log = logging.getLogger("sentinela.sistema")
SO = platform.system()  # 'Windows' | 'Linux' | 'Darwin'


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except Exception as e:  # comando ausente, timeout etc.
        log.debug("Falha ao executar %s: %s", cmd, e)
        return None


# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------
if SO == "Windows":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    HWND_BROADCAST = 0xFFFF
    WM_SYSCOMMAND = 0x0112
    SC_MONITORPOWER = 0xF170
    MOUSEEVENTF_MOVE = 0x0001

    def manter_tela_ligada(ativo: bool):
        flags = ES_CONTINUOUS
        if ativo:
            flags |= ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
        kernel32.SetThreadExecutionState(flags)

    def desligar_tela():
        # PostMessage (assíncrono) evita travar se alguma janela não responder.
        user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)

    def ligar_tela():
        # SC_MONITORPOWER -1 é instável no Win10/11; um "toque" de mouse
        # imperceptível (1px ida e volta) acorda o monitor de forma confiável.
        user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1)
        user32.mouse_event(MOUSEEVENTF_MOVE, 1, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_MOVE, -1, 0, 0, 0)

    def bloquear():
        user32.LockWorkStation()

    def sessao_bloqueada() -> bool:
        # Quando a sessão está bloqueada, o desktop ativo passa a ser o
        # "Winlogon" e OpenInputDesktop falha / retorna outro desktop.
        DESKTOP_SWITCHDESKTOP = 0x0100
        h = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
        if not h:
            return True
        ok = user32.SwitchDesktop(h)
        user32.CloseDesktop(h)
        return not ok

# --------------------------------------------------------------------------
# macOS
# --------------------------------------------------------------------------
elif SO == "Darwin":
    _caffeinate = None

    def manter_tela_ligada(ativo: bool):
        global _caffeinate
        if ativo and (_caffeinate is None or _caffeinate.poll() is not None):
            _caffeinate = subprocess.Popen(["caffeinate", "-d"])
        elif not ativo and _caffeinate is not None:
            _caffeinate.terminate()
            _caffeinate = None

    def desligar_tela():
        _run(["pmset", "displaysleepnow"])

    def ligar_tela():
        _run(["caffeinate", "-u", "-t", "2"])

    def bloquear():
        cg = "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession"
        if _run([cg, "-suspend"]) is None:
            _run(["osascript", "-e",
                  'tell application "System Events" to keystroke "q" using {control down, command down}'])

    def sessao_bloqueada() -> bool:
        r = _run(["python3", "-c",
                  "import Quartz;d=Quartz.CGSessionCopyCurrentDictionary();"
                  "print(bool(d and d.get('CGSSessionScreenIsLocked',0)))"])
        return bool(r and r.stdout.strip() == "True")

# --------------------------------------------------------------------------
# Linux (X11; em Wayland usa loginctl para bloquear)
# --------------------------------------------------------------------------
else:
    _ultimo_reset = 0.0

    def manter_tela_ligada(ativo: bool):
        global _ultimo_reset
        if not ativo:
            return
        if time.time() - _ultimo_reset > 20:  # não precisa a cada frame
            _run(["xset", "s", "reset"])
            if shutil.which("xdg-screensaver"):
                _run(["xdg-screensaver", "reset"])
            _ultimo_reset = time.time()

    def desligar_tela():
        _run(["xset", "dpms", "force", "off"])

    def ligar_tela():
        _run(["xset", "dpms", "force", "on"])
        _run(["xset", "s", "reset"])

    def bloquear():
        if _run(["loginctl", "lock-session"]) is None:
            _run(["xdg-screensaver", "lock"])

    def sessao_bloqueada() -> bool:
        r = _run(["loginctl", "show-session", "self", "-p", "LockedHint", "--value"])
        if r is None or r.returncode != 0:
            r = _run(["bash", "-c",
                      "loginctl show-session $(loginctl | awk '/'$USER'/{print $1;exit}') -p LockedHint --value"])
        return bool(r and r.stdout.strip() == "yes")
