# Sentinela de Tela — Modo Pro

Mantém a tela ligada **somente enquanto uma pessoa autorizada está olhando**, bloqueia o computador quando outra pessoa senta na frente e **fotografa quem tentar acessar** — inclusive quem digitar a senha errada na tela de bloqueio.

Reconhecimento facial leve com OpenCV (YuNet + SFace). Processo completo (motor + painel): **~185 MB de RAM**.

## O que ele faz

| Situação | Ação |
|---|---|
| Pessoa autorizada olhando | Tela permanece ligada |
| Ninguém por N segundos | Desliga a tela |
| Pessoa autorizada volta | Liga a tela |
| Pessoa **não cadastrada** diante do PC desbloqueado | 📸 Foto + **bloqueia** |
| Ausência por X minutos | **Bloqueia** |
| Pessoa não cadastrada parada **na tela de bloqueio** | 📸 Foto |
| **Senha incorreta** digitada na tela de bloqueio *(Windows)* | 📸 Foto no instante da falha |
| Você desbloqueia e houve tentativas | ⚠ Alerta com a foto de quem tentou |

## Painel (Modo Pro)

- **Painel** — status em tempo real, quem está diante da tela, memória, câmera ao vivo, atividade recente, *Pausar* / *Bloquear agora*.
- **Pessoas** — cadastro de várias pessoas com captura ao vivo e barra de progresso; recadastrar, renomear, ativar/desativar, excluir.
- **Tentativas de acesso** — lista com foto, data/hora e tipo; filtros; não vistas em destaque; salvar cópia, abrir pasta, excluir.
- **Configurações** — todos os tempos e regras, PIN do painel, iniciar com o Windows, ativação da foto por senha incorreta.
- **Ícone na bandeja** — fechar a janela mantém a proteção ativa; menu com Abrir / Pausar / Bloquear / Encerrar.
- **PIN do painel** — protege abrir o painel, pausar, encerrar, mudar cadastros e configurações. Ao bloquear o PC, o painel se esconde e só reabre com PIN.

## Instalação (Windows)

1. Instale o **Python 3.10+** marcando *Add python.exe to PATH*.
2. Dê dois cliques em **`iniciar.bat`**. Na primeira vez ele cria o ambiente e abre o painel pedindo o seu cadastro.
3. *(Recomendado)* **Configurações → Foto ao digitar senha incorreta → Ativar** (pede administrador **uma única vez**).
4. *(Recomendado)* Defina um **PIN** e marque **Iniciar automaticamente**.

Quem já usava a versão 1: o `dono.npy` é importado automaticamente como a pessoa "Dono".

### Como funciona a foto da senha incorreta
O Windows registra cada senha errada como **evento 4625**. O `configurar_senha_incorreta.bat` liga essa auditoria e cria uma tarefa agendada (conta SYSTEM) que anota cada falha em `%ProgramData%\SentinelaTela\falhas_login.log`. O Sentinela vê o arquivo crescer e tira a foto na hora — **sem precisar rodar como administrador**. Para desfazer: `configurar_senha_incorreta.bat remover` (como admin).

Mesmo sem isso, com *Vigiar a tela de bloqueio* ligado, qualquer rosto não cadastrado que fique diante da tela bloqueada é fotografado.

## Linha de comando (sem painel)
```bash
python sentinela.py cadastrar --nome "Maria"
python sentinela.py
```

## Arquivos
| Arquivo | Função |
|---|---|
| `app.py` | Inicia o painel (instância única) |
| `interface.py` | Telas (Tkinter) e ícone da bandeja |
| `nucleo.py` | Motor: decisões, vigilância da tela de bloqueio, fotos |
| `visao.py` | Detecção e reconhecimento facial |
| `banco.py` | SQLite: pessoas e eventos (`dados/sentinela.db`) |
| `sistema.py` | Tela, bloqueio, inicialização automática (Windows/Linux/macOS) |
| `config.py` | Configurações e PIN (`config.json`) |
| `capturas/` | Fotos das tentativas |

## Memória (limite 300 MB)
Monitorada a cada 10 s. Se passar do limite: coleta de lixo → menor resolução de análise (320→160 px) → menos análises por segundo. Se ainda precisar: troque `opencv-python` por `opencv-python-headless`, ou remova `pystray`/`pillow` (perde só o ícone da bandeja; fechar a janela passa a minimizar).

## Privacidade (LGPD)
- Pessoas cadastradas: **nenhuma foto é guardada**, só vetores numéricos (biometria — dado sensível, art. 5º II). Ficam apenas neste computador.
- Fotos de tentativas: ficam em `capturas/`, apagadas automaticamente após `dias_retencao_fotos` (padrão 30). Uso recomendado: proteção do próprio equipamento; informe as pessoas do ambiente (ex.: aviso visível) se for um PC compartilhado ou corporativo.
- `config.json` guarda o PIN apenas como hash (PBKDF2).

## Limitações
- **Sem prova de vida**: uma foto da pessoa autorizada pode enganar o reconhecimento. É uma camada extra — **não substitui** a senha / Windows Hello.
- Se o Windows Hello usar a **mesma câmera RGB**, a vigilância da tela de bloqueio pode disputar a câmera. Câmeras IR (Hello) não conflitam.
- À noite, com a tela de bloqueio escura, as fotos podem sair escuras.
- Linux: desligar a tela usa `xset` (X11); foto por senha incorreta só no Windows.
