# Sistema de Finanças

Aplicação Django para controle pessoal de finanças, derivada do `sistema_orcamentos` para reaproveitar autenticação, layout, componentes visuais, segurança e padrões de CRUD.

## Estado atual

O domínio financeiro principal já está implementado.

Funcionalidades disponíveis:

- dashboard financeiro
- contas e saldos
- categorias financeiras
- transações de receita, despesa e transferência
- cartões de crédito
- faturas e compras parceladas
- pagamento de fatura com baixa na conta bancária
- planejamento mensal por categoria
- metas financeiras
- recorrências financeiras com geração de lançamentos futuros
- relatório mensal de fluxo de caixa

Apps antigos (`clientes`, `catalogo`, `orcamentos` e parte de `relatorios`) permanecem instalados apenas por compatibilidade técnica com a base original e migrations antigas. Eles não têm rotas públicas, itens de menu ou registros no admin do sistema financeiro.

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

Receitas e despesas comuns usam `Transacao`.

Transferências usam `Transacao` com conta origem e conta destino.

Compras de cartão usam `LancamentoCartao`, agrupadas por `FaturaCartao`. A compra no cartão não baixa saldo bancário imediatamente. O saldo da conta só é reduzido quando a fatura é paga.

Recorrências geram transações pendentes futuras, evitando automação silenciosa.

## Estrutura principal

- `financeiro`: domínio financeiro principal.
- `core`: dashboard, permissões, contexto, helpers e segurança.
- `usuarios`: autenticação, perfis e controle de acesso.
- `templates/base.html`: layout principal.
- `static/css/style.css`: design visual herdado.
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
