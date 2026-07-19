# Sistema de Finanças

Aplicação Django para controle pessoal e individual de finanças, com autenticação, dashboard e CRUDs financeiros simplificados.

## Funcionalidades disponíveis

- dashboard financeiro
- receitas previstas ou recebidas
- despesas variáveis, fixas e parceladas
- cálculo automático de parcelas
- planejamento semanal
- resumo mensal com gráficos
- metas e reservas simples
- mentoria financeira por IA com OpenAI
- exportação CSV de receitas e despesas

## Requisitos

- Python 3.12
- PostgreSQL 15+ em produção
- Redis 6+ em produção para cache/rate-limit

## Instalação local

```bash
cd /home/rodrigo/Projetos/sistema_financas
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Para habilitar a mentoria financeira da IA, configure:

```bash
OPENAI_API_KEY=...
OPENAI_MENTORIA_MODEL=gpt-5-mini
OPENAI_MENTORIA_FALLBACK_MODEL=gpt-4.1-mini
```

## Uso local

```bash
cd /home/rodrigo/Projetos/sistema_financas
source .venv/bin/activate
python manage.py runserver
```

Acesse:

```text
http://127.0.0.1:8000/
```

## Verificações

```bash
source .venv/bin/activate
python manage.py check
python manage.py test
```

## Fluxo financeiro

Receitas entram pelo menu `Receitas`.

Despesas entram pelo menu `Despesas`, como variáveis, fixas ou parceladas.

O Dashboard mostra quanto está livre para gastar na semana e no mês.

O Controle concentra planejamento semanal, metas e reservas.

Os dados são individuais por usuário, sem empresa, grupos ou perfis de acesso.

## Estrutura principal

- `financeiro`: domínio financeiro principal.
- `core`: dashboard, helpers e segurança.
- `usuarios`: autenticação e visitantes.
- `templates/base.html`: layout principal.
- `static/css/style.css`: design visual.
- `config`: configurações Django e rotas.
- `deploy`: exemplos de produção.

## O que não deve ir para o Git

- `.env` e qualquer arquivo real com segredos
- `db.sqlite3`
- `media/`
- `staticfiles/`
- logs e backups
- `.venv/`

## GitHub

Quando criar o repositório remoto:

```bash
git remote add origin git@github.com:SEU_USUARIO/sistema_financas.git
git push -u origin main
```

## Licença

Este projeto é distribuído sob a **GNU Affero General Public License v3.0** (ver [LICENSE](LICENSE)). Código-fonte: <https://github.com/rigst/sistema_financas>.
