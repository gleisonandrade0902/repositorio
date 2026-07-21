# Plant Growth — Plugin de After Effects

Script (`.jsx`) para o Adobe After Effects que gera uma **planta procedural
crescendo** dentro da composição ativa. A árvore é construída com um algoritmo
recursivo estilo L-system, e o crescimento é animado camada por camada usando
`Trim Paths` em shape layers nativos. Folhas aparecem nas pontas dos galhos
terminais com uma animação de escala.

> Arquivo principal: [`PlantGrowth.jsx`](PlantGrowth.jsx)

## Como funciona

O script cria três coisas para você:

1. **Um null layer** (`Plant Root`) posicionado na base da composição — mova
   esse null para reposicionar a planta inteira.
2. **Um shape layer por galho**, com `Trim End` animado de `0` a `100` —
   é isso que dá o efeito de crescimento.
3. **Uma folha (elipse)** nas pontas dos galhos terminais, com animação de
   `Scale` para "brotar" quando o galho termina.

Cada galho filho começa a crescer depois que uma fração do galho pai
(controlada pelo parâmetro `stagger`) já cresceu — isso dá o efeito de
progressão orgânica de baixo para cima.

## Instalação

1. Copie o arquivo `PlantGrowth.jsx` para a pasta **Scripts** do After Effects:
   - **Windows:** `C:\Program Files\Adobe\Adobe After Effects <versão>\Support Files\Scripts\`
   - **macOS:** `/Applications/Adobe After Effects <versão>/Scripts/`
2. Reinicie o After Effects.
3. Habilite scripts com acesso ao modelo de rede em
   **Edit / Preferences → Scripting & Expressions →
   Allow Scripts to Write Files and Access Network** (necessário só se você
   quiser rodar como painel dockável — para uso simples via menu, não é
   preciso).

## Uso

1. Abra ou crie uma composição (recomendado 1920×1080, mas funciona em
   qualquer tamanho).
2. Rode **File → Scripts → PlantGrowth.jsx**.
3. Ajuste os parâmetros na janela e clique em **Crescer planta**.

Para rodar como **painel dockável**, coloque o arquivo em
`Scripts/ScriptUI Panels/` e depois abra em **Window → PlantGrowth.jsx**.

## Parâmetros

| Parâmetro | Descrição |
|---|---|
| **Iterações** | Profundidade da recursão. Cada nível dobra (ou mais) o número de galhos, então valores > 7 podem ficar lentos. |
| **Galhos/bifurcação** | Quantos galhos filhos saem de cada ponto. `2` = árvore binária clássica. `3+` = arbusto denso. |
| **Ângulo (graus)** | Abertura entre os galhos irmãos. |
| **Variação do ângulo** | Aleatoriedade adicionada ao ângulo — deixa a planta mais orgânica. |
| **Comprimento base** | Tamanho do tronco em pixels. |
| **Redução/nível** | Fator multiplicativo do comprimento a cada nível (`0.72` = cada galho tem 72% do tamanho do pai). |
| **Duração (s)** | Tempo total da animação de crescimento. |
| **Stagger** | Quanto do galho pai cresce antes do filho começar (`0` = simultâneo, `1` = totalmente sequencial). |
| **Tamanho da folha** | Tamanho base das folhas nas pontas. |
| **Seed** | Semente do gerador aleatório — mesma seed sempre produz a mesma planta. |

Use o botão **Nova seed** para experimentar variações rapidamente.

## Personalização rápida (editando o script)

No topo do arquivo há um bloco `DEFAULTS` — mude cores ali:

```javascript
leafColor:   [0.30, 0.75, 0.32],   // RGB de 0 a 1
branchColor: [0.36, 0.22, 0.10],
```

Para folhas em pontos intermediários (não só nas pontas), duplique a chamada
`createLeafLayer(...)` no loop principal e remova a condição `if (!hasChild)`.

## Alternativas mais avançadas

Este script cobre 90% dos casos com o mínimo de fricção. Se você precisar de
algo mais robusto:

- **Painel CEP (HTML/CSS/JS):** UI mais rica com sliders em tempo real.
  Requer habilitar o modo debug de CEP e empacotar em `.zxp`.
- **Plugin nativo C++ (AE SDK):** um efeito aplicável a qualquer camada
  (`.aex`). Requer Xcode/Visual Studio + o AE SDK oficial da Adobe. Só vale
  o investimento se você quiser distribuir comercialmente ou precisa de
  performance em tempo real dentro do render pipeline.

Peça se quiser que eu evolua este projeto para uma dessas alternativas.

## Compatibilidade

Testado conceitualmente contra a API do ExtendScript documentada para
After Effects CC 2018+. Usa apenas propriedades `matchName` estáveis
(`ADBE Vector Shape - Group`, `ADBE Vector Filter - Trim`, etc.), então
deve funcionar em versões futuras sem alteração.
