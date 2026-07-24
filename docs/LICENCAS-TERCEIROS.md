# Licenças de terceiros — Sistema de Finanças

Gerado por `scripts/licencas_terceiros.py` em 2026-07-24 a partir dos pacotes instalados no venv de produção.
Para regenerar: `./venv/bin/python scripts/licencas_terceiros.py`.

O código deste projeto é licenciado sob **AGPL-3.0** (ver `LICENSE`). As bibliotecas abaixo permanecem sob suas licenças originais.

## Dependências diretas

| Pacote | Versão | Licença |
|---|---|---|
| anthropic | 0.117.0 | MIT License |
| asgiref | 3.11.1 | BSD License |
| dj-database-url | 3.0.1 | BSD License |
| Django | 6.0.3 | BSD-3-Clause |
| gunicorn | 23.0.0 | MIT License |
| psycopg | 3.2.12 | LGPL-3.0-only |
| redis | 5.2.1 | MIT License |
| sqlparse | 0.5.5 | BSD License |

## Dependências transitivas

| Pacote | Versão | Licença |
|---|---|---|
| annotated-types | 0.7.0 | MIT License |
| anyio | 4.14.2 | MIT |
| certifi | 2026.6.17 | Mozilla Public License 2.0 (MPL 2.0) |
| distro | 1.9.0 | Apache Software License |
| docstring_parser | 0.18.0 | MIT License |
| h11 | 0.16.0 | MIT License |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD License |
| idna | 3.18 | BSD-3-Clause |
| jiter | 0.16.0 | MIT |
| packaging | 26.1 | Apache-2.0 OR BSD-2-Clause |
| psycopg-binary | 3.2.12 | LGPL-3.0-only |
| pydantic | 2.13.4 | MIT |
| pydantic_core | 2.46.4 | MIT |
| sniffio | 1.3.1 | MIT License / Apache Software License |
| typing_extensions | 4.15.0 | PSF-2.0 |
| typing-inspection | 0.4.2 | MIT |

## Componentes com licença recíproca (copyleft)

Listados para conferência ao redistribuir o código ou ao combinar com componentes fechados. O uso como biblioteca, sem modificação e sem distribuição do binário, não propaga obrigações de abertura.

| Pacote | Versão | Licença |
|---|---|---|
| psycopg | 3.2.12 | LGPL-3.0-only |
| certifi | 2026.6.17 | Mozilla Public License 2.0 (MPL 2.0) |
| psycopg-binary | 3.2.12 | LGPL-3.0-only |

## Notas de manutenção

- **Redis**: o servidor em uso é a série 7.0 (BSD-3-Clause). As versões 7.4 a 7.9 passaram a ser RSALv2/SSPL, que não são licenças livres segundo a OSI. Ao atualizar o servidor, reveja esta seção e a página de licenças do site.
