# Sistema de Finanças

Base Django derivada do `sistema_orcamentos` para construir um sistema de controle pessoal de finanças mantendo o mesmo design, autenticação, estrutura visual e padrões de CRUD.

## Estado atual

Esta pasta é a base inicial do novo projeto. Ela ainda mantém os apps do sistema de orçamentos para preservar uma aplicação executável enquanto o domínio financeiro é implementado.

Próxima evolução planejada:

- criar app `financeiro`
- implementar contas, categorias financeiras e transações
- adaptar o dashboard para indicadores financeiros
- substituir gradualmente clientes, catálogo, orçamentos e relatórios antigos
- manter o layout atual em `templates/base.html` e `static/css/style.css`

## Requisitos

- Python 3.12
- PostgreSQL 15+ em produção
- Redis 6+ em produção para cache/rate-limit

## Instalação local

```bash
cd /home/rodrigo/Projetos/sistema_financas
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Verificações úteis

```bash
python manage.py check
python manage.py test
```

## Estrutura reaproveitada

- `core`: dashboard, permissões, contexto, helpers, segurança e infraestrutura comum.
- `usuarios`: autenticação, perfis e controle de acesso.
- `templates/base.html`: layout principal, navegação, mensagens e scripts comuns.
- `static/css/style.css`: design visual do sistema original.
- `config`: configurações Django e rotas principais.
- `deploy`: exemplos de Gunicorn, Nginx e serviços systemd adaptados para `sistema_financas`.

## Domínio financeiro alvo

Entidades principais planejadas:

- `Conta`
- `CategoriaFinanceira`
- `Transacao`
- `CartaoCredito`
- `FaturaCartao`
- `OrcamentoMensal`
- `MetaFinanceira`

MVP recomendado:

1. Contas
2. Categorias financeiras
3. Transações
4. Dashboard financeiro básico
5. Relatórios por mês, conta e categoria

## Variáveis de ambiente

O projeto lê automaticamente o arquivo `.env` na raiz.

Arquivos base:

- desenvolvimento: `.env.example`
- produção: `.env.production.example`

Variáveis de produção mais importantes:

- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY`
- `DJANGO_HEALTHZ_TOKEN`
- `DJANGO_DEBUG_EXPOSE_MEDIA=False`
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `DJANGO_CACHE_BACKEND=redis`
- `DJANGO_REDIS_CACHE_URL`
- `DJANGO_USE_X_FORWARDED_PROTO=True`
- `DJANGO_USE_MANIFEST_STATICFILES=True`

## Deploy em VPS

Os exemplos em `deploy/` já usam caminhos de produção baseados em:

```text
/var/www/sistema_financas
```

Exemplo de banco PostgreSQL:

```sql
CREATE DATABASE sistema_financas;
CREATE USER sistema_financas_user WITH PASSWORD 'SENHA_FORTE_AQUI';
GRANT ALL PRIVILEGES ON DATABASE sistema_financas TO sistema_financas_user;
```

Exemplo de `DATABASE_URL`:

```text
postgresql://sistema_financas_user:SENHA_FORTE_AQUI@127.0.0.1:5432/sistema_financas
```

## O que não deve ir para o Git

- `.env` e qualquer arquivo real com segredos
- `db.sqlite3`
- `media/`
- `staticfiles/`
- logs e backups

## Git

Este projeto foi inicializado como repositório separado do `sistema_orcamentos`. Quando criar o repositório no GitHub, configure o remoto com:

```bash
git remote add origin git@github.com:SEU_USUARIO/sistema_financas.git
git push -u origin main
```
