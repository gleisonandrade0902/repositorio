# Inscrições da Creche

Sistema local para manter a página de inscrição da creche (portal IPM) sempre atualizada, com **log de todas as atualizações** para apresentar à Câmara / órgãos de controle quando pedido.

Roda 100% na máquina: os dados ficam em `creche.db` (SQLite), dentro desta pasta.

## Fluxo de trabalho

1. **Configurações**: defina a **data de corte** (ex.: `31/03/2027`), os dois links do Google Forms e o nome da creche.
2. **Importar planilha**: envie o `.xls`/`.xlsx`/`.csv` com a lista de alunos. O sistema mostra quem é **novo**, quem foi **alterado** e quem **sai** da lista, além de avisos (datas inválidas, possíveis duplicidades, aluno com 4 anos ou mais que aparece como apto). Só depois de **Confirmar** a lista atual é substituída.
   - Também é possível **adicionar, editar, reordenar e remover** alunos direto pelo sistema (menu *Alunos*).
3. **Gerar HTML**: informe o responsável e o motivo. O sistema:
   - gera o HTML **idêntico ao modelo oficial**, mudando só as datas, os links e as linhas da tabela;
   - grava um registro no **log de atualizações** com data e hora, responsável, motivo, planilha de origem, data de corte, links, a lista completa daquele momento, o que mudou e o HTML publicado.
4. Na tela da atualização, clique em **Copiar HTML** e cole no editor do IPM, no modo *código-fonte*.

## O que muda no HTML a cada geração

| Trecho | Origem |
|---|---|
| `INSCRIÇÃO ESCOLAR 2027` | ano da data de corte |
| `(Atualizado dia 23/09/2026)` | data escolhida em *Gerar HTML* (padrão: hoje) |
| `…3 ANOS ATÉ 31/03/2027` e os textos `Idade em 31/03/2027` | data de corte |
| `new Date(2027, 2, 31)` nos dois botões | data de corte (mês em JavaScript começa em 0) |
| `forms.gle/…` (apto / menor de 18 meses) | Configurações |
| Linhas da tabela | lista atual de alunos |

Todo o resto (CSS, textos, critérios, estrutura) sai exatamente como no original. O teste automatizado `tests/test_creche.py` compara o resultado **byte a byte** com `tests/referencia_ipm.html`.

### Regras da tabela

- **Nascimento** sai sempre mascarado: `**/MM/AAAA` (LGPD). A data completa, se vier na planilha, fica só no banco local.
- Situação em **verde** (`status-ok`): LISTA DE ESPERA, MATRICULADO(A), APTO, CLASSIFICADO(A), APROVADO(A). Qualquer outra aparece em **vermelho** (`status-nok`).
- Se a coluna **Observação** estiver preenchida, a célula de situação usa o formato com dois parágrafos (situação + texto), igual ao dos alunos com matrícula por prioridade no modelo original.
- A ordem da tabela é a ordem das linhas da planilha.
- Colunas extras da planilha (CPF, filiação, endereço…) são ignoradas e nunca vão para a página.

## Planilha

A primeira aba é lida. Cabeçalhos reconhecidos (sem diferenciar acentos ou maiúsculas):

| Campo | Exemplos de cabeçalho aceitos |
|---|---|
| Inscrição | Inscrição, Nº, Protocolo (vazio vira `-`) |
| Nome do candidato **(obrigatório)** | Nome do Candidato, Nome, Aluno, Nome completo da criança |
| Nascimento | Nascimento, Data de nascimento, DN |
| Situação | Situação, Status |
| Data inscrição | Data Inscrição, Data da inscrição, Carimbo de data/hora (Google Forms) |
| Observação | Observação, Obs |

Colunas com "mãe", "pai" ou "responsável" no nome são ignoradas. Em *Importar planilha* há um botão para baixar a **planilha modelo**.

## Log de atualizações e integridade

- Nenhum registro do log pode ser editado ou apagado pelo sistema.
- Cada registro guarda o **SHA-256 do HTML** e um **hash encadeado** com o registro anterior. Se alguém alterar ou apagar um registro direto no banco, a tela *Log de atualizações* e o relatório acusam **"violado"**.
- **Relatório para a Câmara**: *Log de atualizações → Gerar relatório* (com filtro de período) → *Imprimir / salvar PDF*. Traz todas as atualizações com responsável, motivo e a lista de quem entrou, saiu ou mudou.
- **Exportar log (.csv)** para Excel.
- Em cada atualização: baixar o HTML exato que foi publicado e a **lista daquele momento em .xlsx**.

## Instalação e execução

Requisitos: Python 3.10+.

**Windows**: dê dois cliques em `run.bat`. O navegador abre em <http://127.0.0.1:5001>.

**Linux/macOS**:

```bash
cd creche
./run.sh
```

Ou manualmente:

```bash
cd creche
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                    # http://127.0.0.1:5001  (PORT=8080 python app.py para outra porta)
```

## Testes

```bash
cd creche
python -m unittest discover -s tests -v
```

## Backup

Todo o sistema (lista, configurações e log) está em **`creche/creche.db`**. Copie esse arquivo com frequência para um pen-drive ou para a nuvem: ele é a prova das atualizações. Para restaurar, basta substituir o arquivo.

## Estrutura

```
creche/
├── app.py              # rotas (painel, alunos, importação, geração, log)
├── models.py           # Configuracao, Aluno, Atualizacao (log)
├── planilha.py         # leitura .xls/.xlsx/.csv, normalização, validação e comparação
├── publicacao.py       # geração do HTML do IPM + cadeia de hashes do log
├── templates/
│   ├── ipm/pagina_inscricao.html   # modelo oficial da página (não alterar a formatação)
│   └── ...                          # telas do sistema
├── static/style.css
└── tests/              # teste byte a byte contra o HTML oficial
```
