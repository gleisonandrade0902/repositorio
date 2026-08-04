# Gerador de Diário Oficial

Programa que junta vários PDFs (decretos, portarias, extratos de contrato,
avisos de licitação etc.) em um único arquivo — o Diário Oficial da edição —
aplicando automaticamente em cada página o cabeçalho padrão (brasão, título,
nome do município, data e número da edição) e a numeração de páginas, no
mesmo modelo do Diário Oficial Eletrônico usado como referência.

Para gerar uma nova edição você só precisa: colocar os PDFs na pasta
`entrada/` e configurar o número da edição (e outros dados que mudam pouco,
como município e lei de instituição do Diário). Não é necessário editar cada
PDF nem montar o cabeçalho manualmente — isso é feito automaticamente.

## Como usar (modo rápido, com o executável)

1. Gere o executável uma única vez (veja "Gerando o executável" abaixo), ou
   peça para alguém da equipe técnica gerar e te enviar o arquivo
   `GeradorDiarioOficial` (Linux/macOS) ou `GeradorDiarioOficial.exe`
   (Windows).
2. Coloque, na mesma pasta do executável, os PDFs a publicar dentro da pasta
   `entrada/` — nomeie os arquivos com um número na frente para controlar a
   ordem em que entram no Diário, por exemplo:
   ```
   entrada/
     01_decreto_2296.pdf
     02_extrato_contrato_051.pdf
     03_aviso_contratacao_057.pdf
   ```
3. Dê duplo clique no executável. Na janela que abrir, confira/edite:
   - Município e UF
   - Ano do Diário (ex.: `XIII`) e Nº da edição
   - Data da edição (deixe em branco para usar a data de hoje)
   - Lei que instituiu o Diário (número e data) e o site da prefeitura
   - Pasta de entrada / pasta de saída (se quiser usar outras)
4. Clique em **Gerar Diário Oficial**. O arquivo final é salvo em
   `saida/Diario_Oficial_Edicao_<numero>.pdf`.

As configurações digitadas ficam salvas em `config.json`, então da próxima
vez você só precisa trocar o número da edição (e adicionar os novos PDFs).

## Como usar (a partir do código-fonte)

Requer Python 3.9+.

```bash
cd diario_oficial
pip install -r requirements.txt

# Interface gráfica:
python gerar_diario.py

# Ou em modo texto/terminal (útil para automatizar):
python gerar_diario.py --cli --config config.json
```

## Gerando o executável

Isso empacota o programa (com a interface gráfica) em um único arquivo
executável, para rodar em outro computador sem precisar instalar Python.

**Linux/macOS:**
```bash
cd diario_oficial
./build_exe.sh
```

**Windows:**
```bat
cd diario_oficial
build_exe.bat
```

O executável final fica em `dist/GeradorDiarioOficial` (ou `.exe`). Distribua
esse arquivo junto com as pastas `ativos/`, `entrada/`, `saida/` e o
`config.json` (o programa recria essas pastas/arquivos automaticamente ao
lado do executável na primeira execução, caso não existam).

## Configuração (`config.json`)

| Campo | Descrição |
|---|---|
| `municipio` | Nome do município, ex.: `Carmópolis de Minas` |
| `uf` | Sigla do estado, ex.: `MG` |
| `ano_diario` | Ano de existência do Diário, como aparece no cabeçalho (ex.: `XIII`) |
| `numero_edicao` | Número da edição — **o principal campo a trocar a cada publicação** |
| `data_edicao` | Data no formato `DD/MM/AAAA`; se vazio, usa a data atual |
| `lei_numero` / `lei_data` | Lei municipal que instituiu o Diário Oficial |
| `site` | Site exibido no rodapé da última página |
| `logo` | Caminho da imagem do brasão/logo (relativo à pasta do programa) |
| `pasta_entrada` | Pasta com os PDFs a publicar |
| `pasta_saida` | Pasta onde o Diário final é salvo |

## Como o cabeçalho é montado

Cada PDF colocado em `entrada/` é tratado como um "ato" a publicar: o
programa cria uma página nova para cada página desses PDFs, desenha o
cabeçalho (brasão + título + edição) no topo e encaixa o conteúdo original
logo abaixo, redimensionado para caber na área útil da página — por isso
funciona com PDFs que **não têm** cabeçalho algum, sem precisar reformatar
nada manualmente. A numeração de página e o rodapé (linha + site) seguem o
mesmo padrão do modelo de referência, sendo o rodapé completo (linha + link
do site) reservado para a última página do Diário.

A imagem do brasão em `ativos/brasao_exemplo.png` é apenas um exemplo
extraído do PDF de referência usado para desenhar este layout — substitua
pelo brasão oficial do seu município antes de publicar um Diário real.
