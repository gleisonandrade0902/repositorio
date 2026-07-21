# Plant Growth Animator — Plugin de After Effects

Script (`.jsx`) para o Adobe After Effects que **anima o crescimento de uma
planta desenhada por você**. Você atribui suas próprias camadas a cada papel
(caule, raízes, galhos, folhas, frutos) e o script cria as keyframes de
crescimento na ordem orgânica.

> Arquivo principal: [`PlantGrowth.jsx`](PlantGrowth.jsx)

## Modelo

Você desenha (ou importa) a arte da sua planta como camadas separadas. Aí,
na janela do script, aponta:

| Papel      | Obrig.? | Qtd. | Como cresce |
|------------|:------:|:----:|-------------|
| **Caule**  | sim | 1  | de baixo pra cima |
| **Raízes** | não | N  | de cima pra baixo, em paralelo ao caule |
| **Galhos** | não | N  | escalonados, começam quando o caule já cresceu um pouco |
| **Folhas** | não | N  | *pop-in* (scale com overshoot) depois dos galhos |
| **Frutos** | não | N  | *pop-in* no final |

## Como o script decide a técnica de animação

Para cada camada atribuída, o script escolhe automaticamente:

- **Se for um shape layer com um path** → adiciona (ou reaproveita) um
  `Trim Paths` e anima `End: 0 → 100`.
  ⚠️ Desenhe o path começando pela base do crescimento (o pé do caule para
  o caule; a base do galho para os galhos; a base do talo da raiz para as
  raízes). O trim segue a direção do path.
- **Qualquer outra camada** (raster, texto, sólido, footage, precomp) →
  anima `Scale Y: 0 → 100` com o `Anchor Point` movido pra base correta
  (bottom para caule/galhos, top para raízes, centro para folhas/frutos).
  A posição é compensada automaticamente pra imagem não pular.

Isso significa que **funciona igual bem** com plantas vetorizadas no AE ou
com PNGs desenhados no Photoshop/Illustrator.

## Instalação

Copie `PlantGrowth.jsx` para uma das pastas:

- **Menu**: `.../After Effects .../Support Files/Scripts/`
  → Aparece em **File → Scripts → PlantGrowth.jsx**
- **Painel dockável**: `.../After Effects .../Support Files/Scripts/ScriptUI Panels/`
  → Aparece em **Window → PlantGrowth.jsx**

Para o painel dockável funcionar, ative
**Edit / Preferences → Scripting & Expressions → Allow Scripts to Write
Files and Access Network**.

Reinicie o AE após copiar.

## Fluxo de uso

1. Abra a comp com a arte da planta.
2. Rode o script.
3. Para cada papel:
   - Selecione a(s) camada(s) correspondente(s) na comp.
   - Clique **Definir da seleção** (caule) ou **Adicionar da seleção**
     (raízes / galhos / folhas / frutos).
4. Ajuste **Duração total** e as frações de tempo (opcional).
5. Clique **Animar crescimento**.

O botão **Remover animação** limpa os keyframes de `Scale` e `Trim Paths`
de todas as camadas atribuídas — útil pra reanimar com outros tempos.

## Parâmetros de tempo

| Parâmetro | Descrição |
|---|---|
| **Início (s)** | Momento absoluto na timeline em que a planta começa. |
| **Duração total (s)** | Tempo até a planta estar completa (caule + tudo). |
| **Fração caule** | Fração da duração dedicada ao caule (padrão `0.55`). Raízes crescem no mesmo intervalo. |
| **Galhos após (0–1)** | Fração do caule que precisa crescer antes de galhos começarem (padrão `0.35`). |
| **Frutos após (0–1)** | Fração da duração total até frutos começarem a brotar (padrão `0.75`). |

Múltiplos galhos, folhas e frutos são automaticamente **escalonados dentro
da sua janela de tempo** — se você tem 5 folhas, elas brotam em sequência
suave em vez de todas ao mesmo tempo.

## Dicas de arte

- **Caule com curva?** Desenhe como shape layer, path começando no chão.
  O `Trim Paths` respeita a curva perfeitamente.
- **Galhos angulados?** Cada um pode ser uma camada separada (shape ou
  raster). Se for raster, coloque a "base" do galho na parte de baixo da
  camada — o script vai crescer a partir dali.
- **Folhas em várias posições?** Cada folha é uma camada. Você posiciona
  onde quer; o script só faz o brotamento no lugar.
- **Reanimar depois de mexer na arte:** clique **Remover animação** →
  ajuste → **Animar crescimento** de novo.

## Limitações conhecidas

- Camadas de câmera / luz / null não fazem sentido como partes da planta e
  são ignoradas silenciosamente (não têm `sourceRectAtTime`).
- Para shape layers com **múltiplos paths dentro do mesmo grupo**, o
  `Trim Paths` afeta todos juntos. Se quiser controle independente, separe
  em shape layers distintos e atribua cada um como um galho.
- O script **não conecta parentesco** entre galhos e caule automaticamente.
  Se você quer que galhos sigam movimento do caule, use pick-whip do AE
  antes de animar.

## Alternativas mais avançadas

- **Painel CEP (HTML/CSS/JS):** UI mais rica com sliders em tempo real,
  drag-and-drop de camadas. Requer empacotar `.zxp`.
- **Plugin nativo C++ (AE SDK):** um efeito aplicável a qualquer camada
  (`.aex`). Requer Xcode/Visual Studio + o AE SDK oficial da Adobe. Só
  vale a complexidade se você quiser distribuir comercialmente.

Peça se quiser que eu evolua este projeto pra uma dessas alternativas.

## Compatibilidade

Testado conceitualmente contra a API do ExtendScript documentada para
After Effects CC 2018+. Usa apenas `matchName`s estáveis
(`ADBE Vector Filter - Trim`, `ADBE Root Vectors Group`, etc.) e a API
clássica de shape layer, então deve funcionar sem alteração em versões
futuras.
