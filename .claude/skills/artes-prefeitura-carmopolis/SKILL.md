---
name: artes-prefeitura-carmopolis
description: Criar, revisar ou padronizar artes de comunicação da Prefeitura Municipal de Carmópolis de Minas (ASCOM) — posts de feed 4:5, carrosséis informativos, datas comemorativas e campanhas de saúde/serviço — seguindo a identidade visual usada nas últimas peças (azul institucional, verde, âmbar, Montserrat, assinatura com brasão). Use sempre que o pedido envolver arte, post, carrossel, card, banner ou peça para a prefeitura, uma secretaria ou um programa municipal.
---

# Artes da Prefeitura de Carmópolis de Minas (ASCOM)

Padrão extraído das peças publicadas entre set/out de 2026 (Plano Diretor, Suplementação Orçamentária, Outubro Rosa, Dia das Crianças, Dia do Professor). Exemplos em `referencias/` — **abra-os antes de criar** uma peça nova para calibrar o olho.

| Arquivo de referência | Família |
|---|---|
| `01-institucional-capa-carrossel-azul.jpg` | Institucional — capa de carrossel 4:5 |
| `02-institucional-capa-quadrada.jpg` | Institucional — capa de carrossel 1:1 |
| `03-institucional-slide-interno.jpg` | Institucional — slide interno (fundo branco) |
| `04-comemorativa-dia-do-professor.jpg` | Data comemorativa — clean/claro |
| `05-comemorativa-dia-das-criancas.jpg` | Data comemorativa — lúdica/3D |
| `06-campanha-outubro-rosa.jpg` | Campanha temática (saúde) |

## 1. Duas famílias de peça — decidir primeiro

**A. Institucional / informativa** (prestação de contas, leis, orçamento, obras, serviços, programas, "entenda", "o que é"):
identidade rígida — azul-marinho + verde + âmbar, Montserrat, ícones flat, carrossel numerado. É o padrão-base da prefeitura.

**B. Comemorativa / campanha** (datas, meses temáticos — Outubro Rosa, Novembro Azul, Setembro Amarelo, Dia do Professor etc.):
paleta e ilustração livres, ditadas pelo tema; **o que não muda** é a estrutura (data no topo, título-herói no centro, assinatura com brasão embaixo) e a tipografia de apoio em Montserrat.

## 2. Paleta (valores medidos nas artes)

### Institucional (família A)
| Token | HEX | Uso |
|---|---|---|
| `--azul-institucional` | `#12355B` | Fundo das capas (Plano Diretor) |
| `--azul-profundo` | `#0E2550` | Fundo de capa alternativo / gradiente com `#163058` |
| `--azul-texto` | `#153579` | Títulos e círculos de ícone em slides brancos |
| `--verde` | `#137E30` | Marca-texto do título, barra sob o título, número do slide, paginação ativa |
| `--verde-claro` | `#5FAF41` | Círculos de ícone sobre fundo azul |
| `--ambar` | `#E9A93B` | Botão-seta "deslize", sublinhado do contador `1/10`, detalhes |
| `--vermelho` | `#D0202E` | Somente ícones (saúde, alerta) — nunca em blocos grandes |
| `--branco` | `#FFFFFF` | Texto sobre azul / fundo de slides internos |
| `--cinza-paginacao` | `#C9CED8` | Bolinhas inativas da paginação |

Formas decorativas: círculos grandes em azul ~6% mais claro que o fundo (`#1D325F` sobre `#0E2550`), cortados pela borda; ou ondas concêntricas em linha fina branca com ~10% de opacidade (Plano Diretor).

### Comemorativas já usadas (família B — referência, não regra)
| Peça | Cores |
|---|---|
| Dia do Professor | fundo `#F4F4F6`→branco, data em roxo `#623383`, script cinza `#5A5A5A`, toques rosa |
| Dia das Crianças | azul-céu `#45A4DA` + roxo `#764594`/`#79569A`, amarelo dos aviõezinhos, letras 3D |
| Outubro Rosa | rosa escuro `#BC126A`, rosa médio `#E97B98`, rosa claro `#F3BCCF` |

Regra de recorrência: **roxo** tem aparecido como cor da data no topo das comemorativas — usar quando o tema não impuser outra cor.

## 3. Tipografia
- **Família principal: Montserrat** (Google Fonts, gratuita; no Illustrator/Canva usar a mesma).
  - Títulos institucionais: **ExtraBold/Black (800–900), CAIXA ALTA**, entrelinha ~1.05 (ex.: "O QUE É SUPLEMENTAÇÃO ORÇAMENTÁRIA?").
  - Títulos de capa estilo "frase": **Bold (700) em caixa normal** (ex.: "Plano Diretor: o futuro de Carmópolis começa a ser desenhado").
  - Corpo/subtítulo: **Regular (400)**, destaques no corpo em **ExtraBold** na cor do título.
  - Data no topo das comemorativas: **SemiBold/Bold, CAIXA ALTA** ("15 DE OUTUBRO").
- **Script de apoio** (só comemorativas): manuscrita fina e elegante para o nome da data ("dia do professor", "Rosa") — ex.: *Allura*, *Great Vibes*, *Dancing Script*. Nunca em textos informativos.
- Faixas de texto sobre foto (Outubro Rosa): Montserrat Bold caixa alta, branco sobre tarja sólida da cor do tema, uma tarja por linha.
- Tamanhos de referência no canvas 1080×1350: título capa 64–80px · título interno 48–56px · corpo 28–32px · assinatura 18/24px. Corpo nunca abaixo de 26px (leitura no celular).

## 4. Assinatura (obrigatória em toda peça)
- **Brasão oficial do município** (colorido, com faixa "CARMÓPOLIS DE MINAS", datas 1708 / 27-12-48) + texto em duas linhas:
  - linha 1: `PREFEITURA MUNICIPAL DE` (ou `PREFEITURA DE` nas comemorativas) — Montserrat Medium, caixa alta, menor;
  - linha 2: `CARMÓPOLIS DE MINAS` — Montserrat ExtraBold, caixa alta.
- Posições usadas: **centralizada embaixo** (padrão comemorativas e Plano Diretor: brasão à esquerda + texto à direita, em linha) ou **canto inferior esquerdo empilhado** (brasão sobre o texto — capas institucionais 1:1). Em slides internos a assinatura pode ser omitida; na capa e no último slide é obrigatória.
- Texto da assinatura em branco sobre fundo escuro, em `--azul-texto`/cinza-escuro sobre fundo claro.
- Nunca recolorir, distorcer, aplicar sombra ou contorno no brasão. Área de respiro mínima = altura da coroa do brasão. Arquivo oficial: Biblioteca de Arquivos do CreativeOS › *Logos & Identidade* (pedir ao Gleison se não estiver disponível — **não redesenhar o brasão**).

## 5. Formatos e grid
| Formato | Pixels de entrega | Uso |
|---|---|---|
| Feed retrato 4:5 | **2250 × 2812** (1080×1350 exportado a 208,33%) | padrão atual de posts e capas |
| Quadrado 1:1 | **1688 × 1688** | carrosséis informativos longos |
| Stories/Reels 9:16 | 1080 × 1920 | adaptação; manter 250px livres no topo e embaixo |

- Margem de segurança: **~7% da largura** (≈75px em 1080). Títulos alinhados à esquerda nas institucionais; centralizados nas comemorativas.
- Exportar JPG qualidade alta (sRGB). Nome de arquivo: `tema-NN.jpg` (ex.: `suplementacao-orcamentaria-03.jpg`), igual ao padrão já usado.

## 6. Componentes de carrossel institucional
1. **Capa** (fundo azul): contador `1/N` no topo direito com sublinhado âmbar *ou* paginação de bolinhas embaixo; ícone/ilustração flat do tema; título com palavra-chave em **marca-texto verde** (retângulo `--verde` atrás do texto, cantos levemente arredondados); subtítulo-chamada ("Entenda de forma simples…", "Deslize e veja…"); **botão-seta âmbar** circular no canto inferior direito; assinatura.
2. **Slides internos** (fundo branco): número do slide em **círculo verde** no topo esquerdo; título `--azul-texto` caixa alta ExtraBold; **barra verde** curta (≈90×8px) sob o título; parágrafo com destaques em negrito; bloco "ícone em círculo azul + frase-resumo em negrito + explicação"; paginação de bolinhas centralizada embaixo com a ativa em pílula verde.
3. **Último slide**: chamada para ação (onde acessar, telefone, endereço, link na bio) + assinatura completa.
- Um conceito por slide; no máximo ~40 palavras de corpo por slide. Linguagem simples, direta, sem juridiquês (é o tom das peças "O que é…?").

## 7. Ícones e imagens
- Institucional: ícones **flat**, formas geométricas simples, sem contorno, nas cores da paleta (ambulância, coração, "+", mapa do município com pontos de serviço). Nada de 3D ou foto de banco nessa família.
- Comemorativa: ilustração 3D ou vetorial temática é permitida (Dia das Crianças), assim como silhuetas/recortes (Outubro Rosa) e elementos delicados (estrelinhas, corações, traços) no estilo clean.
- Mapa do município (contorno branco) é um ativo recorrente para temas de cidade/planejamento.

## 8. Fluxo de trabalho
1. Classificar a peça (A ou B) e o formato. Confirmar com o pedido: tema, secretaria, data, textos obrigatórios, nº de slides.
2. Escrever/revisar a copy primeiro (títulos curtos, frase-chave para o marca-texto verde). Revisar ortografia e acentuação — inclusive "CARMÓPOLIS" com acento.
3. Montar o layout:
   - **HTML → PNG (Claude)**: partir de `templates/base.html` (já contém tokens, Montserrat e os 3 layouts) e renderizar com Playwright em `deviceScaleFactor: 2.0833` para 2250×2812, ou 1080×1350 em escala 1 para prévia.
   - **Illustrator/Photoshop/Canva**: usar a paleta da seção 2 como swatches e os tamanhos da seção 3; artboard 1080×1350 exportado a 208,33% = 2250×2812.
4. Checklist antes de entregar:
   - [ ] Brasão oficial + "PREFEITURA (MUNICIPAL) DE CARMÓPOLIS DE MINAS" presente e legível
   - [ ] Cores somente da paleta (família A) / coerentes com o tema (família B)
   - [ ] Montserrat em todos os textos (exceto script decorativo)
   - [ ] Margem de 7% respeitada; nada cortado no grid do Instagram (4:5)
   - [ ] Carrossel: numeração/paginação correta em todos os slides, slide final com CTA
   - [ ] Sem dados pessoais de cidadãos (LGPD) e sem promoção pessoal de agentes públicos (art. 37, §1º, CF — impessoalidade: nada de nome/foto de prefeito ou secretário como destaque da peça)
   - [ ] Em período eleitoral, conferir restrições de publicidade institucional antes de publicar
5. Entregar a arte + legenda sugerida (tom institucional, frase de abertura forte, 3–5 hashtags locais, ex.: `#CarmópolisDeMinas #PrefeituraDeCarmópolis`).

## 9. O que evitar
- Misturar a paleta institucional com a de uma comemorativa na mesma peça.
- Gradientes coloridos, neon, sombras pesadas ou mais de 2 famílias tipográficas.
- Texto corrido longo em imagem (vira carrossel ou vai para a legenda).
- Logo de partido, slogan de gestão ou cores de campanha política.
