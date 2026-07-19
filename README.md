# GeSUAS Local

Sistema local de gestão da assistência social inspirado no GeSUAS, para uso em CRAS, CREAS e equipes técnicas do SUAS. Roda 100% localmente — os dados ficam num arquivo SQLite na própria máquina; não há dependência de servidores externos.

## Recursos

- **Cadastro de famílias** com estrutura completa: identificação, endereço, condições de moradia, renda, benefícios (Bolsa Família / Auxílio Brasil, BPC, benefícios eventuais), acompanhamento SUAS (PAIF, PAEFI, SCFV, medida socioeducativa), vulnerabilidades e observações.
- **Composição familiar sem limites**: cada família pode ter quantos membros forem necessários, com estrutura parental (Responsável Familiar, Cônjuge, Filho(a), Enteado(a), Neto(a), Pai, Mãe, Sogro(a), Irmão(ã), Agregado(a), Outro).
- **Prontuário individual por membro** com documentação (CPF, RG, NIS, título, CTPS, certidões), educação, trabalho/renda, saúde (deficiência, CID, medicações, gestante/lactante), grupos populacionais tradicionais e situações de vulnerabilidade (situação de rua, trabalho infantil, exploração sexual, violência doméstica, uso de substâncias, LGBTQIA+, imigrante, medida socioeducativa).
- **Evolução do prontuário no tempo** — timeline com data/hora, tipo (escuta qualificada, visita domiciliar, atendimento particularizado, grupo, PAIF, PAEFI, estudo social, parecer técnico etc.), técnico responsável, descrição, conduta, encaminhamentos e próximos passos.
- **Atendimentos** por família ou membro específico (acolhida, escuta, visita domiciliar, grupo, benefício eventual, etc.).
- **Encaminhamentos intersetoriais** com controle de contra-referência e status (Pendente, Em andamento, Atendido, Recusado, Cancelado).
- **Relatórios** prontos para impressão / salvar como PDF pelo navegador:
  - Famílias cadastradas (com indicadores de pobreza e extrema pobreza)
  - Perfil populacional (faixa etária, sexo, raça/cor, deficiência)
  - Vulnerabilidades e riscos
  - Atendimentos por período, tipo e técnico
  - Ficha completa da família
  - Prontuário individual

## Requisitos

- Python 3.10 ou superior
- Navegador web (Chrome, Firefox, Edge, Safari — qualquer um moderno)

## Instalação

Clone o repositório e crie um ambiente virtual:

```bash
git clone <URL-DO-REPO>
cd repositorio

python3 -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

## Executando

```bash
python app.py
```

Depois abra no navegador: <http://127.0.0.1:5000>

O arquivo do banco de dados (`gesuas_local.db`) será criado automaticamente na primeira execução, na raiz do projeto. Faça backup deste arquivo para preservar seus dados.

Para rodar em outra porta:

```bash
PORT=8080 python app.py
```

## Backup

Todos os dados ficam num único arquivo: `gesuas_local.db`.
Basta copiá-lo para um pen-drive / nuvem para ter um backup completo. Restaurar é substituir o arquivo pelo backup.

## Estrutura do projeto

```
repositorio/
├── app.py                # Aplicação Flask (rotas)
├── models.py             # Modelos de dados (SQLAlchemy)
├── requirements.txt      # Dependências
├── static/
│   └── style.css         # Estilos
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── familias/         # Lista, formulário e detalhe da família
│   ├── membros/          # Formulário e prontuário do membro
│   ├── evolucoes/        # Formulário de evolução do prontuário
│   ├── atendimentos/     # Lista e formulário de atendimentos
│   ├── encaminhamentos/  # Formulário de encaminhamentos
│   └── relatorios/       # Todos os relatórios
└── gesuas_local.db       # Banco SQLite (criado na 1ª execução)
```

## Aviso legal

Este sistema não é oficial nem tem relação com o GeSUAS comercial. Foi criado para uso interno em equipes de assistência social como ferramenta local de apoio à gestão de prontuários. Cuide da segurança física do computador onde ele está instalado e faça backup periódico do arquivo `gesuas_local.db` — os dados são sensíveis e devem ser protegidos conforme a LGPD (Lei nº 13.709/2018).
