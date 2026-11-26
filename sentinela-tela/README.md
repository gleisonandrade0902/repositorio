# Sentinela de Tela

Mantém a tela ligada **somente enquanto o dono está olhando**. Usa a webcam + reconhecimento facial leve (OpenCV YuNet + SFace).

| Situação | Ação |
|---|---|
| Dono olhando para a tela | Tela permanece ligada (bloqueia o descanso de tela) |
| Ninguém por `segundos_para_desligar_tela` | Desliga a tela |
| Dono volta | Liga a tela |
| Outra pessoa sem o dono (confirmada `verificacoes_para_estranho` vezes) | **Bloqueia** o computador |
| Ausente por `minutos_para_bloquear` | **Bloqueia** o computador |

Medido: **~150 MB de RAM**, ~25 ms por análise (3 análises/s, 1 thread de CPU).

## Instalação (Windows)
Dê dois cliques em `iniciar.bat`. Na primeira vez ele cria o ambiente, baixa os modelos (~39 MB) e pede o cadastro do rosto.

## Manual (Windows / Linux / macOS)
```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\...
python baixar_modelos.py
python sentinela.py cadastrar      # fique sozinho(a) diante da câmera, boa luz
python sentinela.py --preview      # 1º teste: mostra caixas DONO/OUTRO e a similaridade
python sentinela.py                # uso normal
```
Iniciar com o Windows: atalho de `iniciar.bat` em `shell:startup` (Win+R).

## Ajustes (`config.json`)
- `limiar_reconhecimento` (0.40): subir = mais rígido (menos risco de aceitar outra pessoa, mais falso "estranho"). Calibre com `--preview`.
- `exigir_olhar_para_tela`: dono de cabeça virada conta como "não olhando" (tela desliga após o tempo de graça).
- `bloquear_estranho_mesmo_com_dono`: `true` bloqueia se alguém aparecer **atrás** de você.
- `limite_memoria_mb` (300): ver abaixo.

## Se precisar de mais de 300 MB
O programa monitora o próprio consumo a cada 10 s. Ao passar do limite ele, em degraus: força coleta de lixo → reduz resolução de análise (320→256→192→160 px) → reduz frequência (3→2→1 análise/s), registrando no `sentinela.log`. Se mesmo assim passar, causas típicas e soluções:
1. **`opencv-python` completo** (~80 MB a mais por GUI/Qt): use `opencv-python-headless` (perde só o `--preview`).
2. **Muitos rostos na imagem**: só os 3 maiores são reconhecidos (`max_rostos` em `visao.py`).
3. **Vazamento de driver de câmera**: o programa reabre a câmera ao falhar; atualizar o driver resolve.
4. Como último recurso, trocar SFace por modelo quantizado int8 (`face_recognition_sface_2021dec_int8.onnx`, ~10 MB, um pouco menos preciso).

## Privacidade (LGPD)
Nenhuma imagem é gravada. `dono.npy` guarda apenas vetores numéricos (biometria derivada — dado sensível, art. 5º II): fica só nesta máquina e está no `.gitignore`. Apague-o para revogar.

## Limitações honestas
- **Não tem prova de vida**: uma foto do dono pode enganar o reconhecimento. É uma camada de conveniência/privacidade, **não** substitui senha/Windows Hello.
- Linux: desligar a tela usa `xset` (X11). Em Wayland, só o bloqueio (`loginctl`) é garantido.
- O LED da webcam fica aceso enquanto monitora (é desligado durante o bloqueio).
