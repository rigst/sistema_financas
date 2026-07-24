# Conformidade legal — LGPD e Marco Civil

Como o sistema registra o aceite dos termos, por quanto tempo guarda os registros de
acesso e o que fazer para publicar uma versão nova das políticas.

## 1. Registro de aceite

O app `legal` guarda dois modelos.

**`DocumentoLegal`** — uma linha por *versão* de cada documento (Termos de Uso e Política
de Privacidade). Ciclo de vida: `rascunho` → `publicado` → `arquivado`. Ao publicar, o
sistema congela o HTML renderizado e o `sha256` do texto; a partir daí a versão é imutável.

**`AceiteLegal`** — a prova. Cada linha guarda:

| Campo | Para que serve |
|---|---|
| `documento` | qual versão foi aceita (FK `PROTECT`: não some por cascade) |
| `usuario` / `usuario_label` | quem aceitou; o label é congelado e sobrevive à exclusão da conta |
| `e_visitante` | se era conta temporária |
| `ip`, `user_agent`, `aceito_em` | de onde, com quê e quando |
| `session_key` | vincula o aceite anônimo à sessão |
| `origem` | cadastro, visitante, re-aceite ou uso anônimo |
| `documento_sha256` | hash do texto **no momento do aceite** |
| `evidencia` (JSON) | host, path, método, `Referer`, `X-Forwarded-For` bruto, idioma e as versões vigentes na hora |

O ponto mais importante do desenho: **o aceite sobrevive à exclusão do usuário.** Contas
de visitante são apagadas ao expirar (`usuarios/visitantes.py`, `limpar_dados_visitante`
chama `user.delete()`). Por isso `usuario` é `SET_NULL` e existe o `usuario_label`
congelado — com `CASCADE`, a prova sumiria junto com o visitante.

### Onde o aceite é capturado

- **Acesso visitante** (`usuarios/views.py`): o checkbox é validado **antes** de criar a
  conta. Sem aceite, nenhum usuário é criado.
- **Login normal**: sem checkbox. Quem já tem conta já aceitou; se a versão mudou, o
  middleware trata.
- **Versão nova** (`legal/middleware.py`): `AceiteObrigatorioMiddleware` redireciona
  qualquer usuário autenticado com aceite pendente para `/legal/reaceite/`, liberando só
  as rotas da allowlist (páginas legais, logout, admin, estáticos).

O checkbox nasce sempre desmarcado (`initial=False`) e é obrigatório no **servidor**
(`required=True`) — burlar o HTML no navegador não passa pela validação do formulário.

### Extrair evidência

No admin, em *Conformidade legal → Aceites*: filtre por documento, versão, origem ou
data e use a ação **"Exportar seleção em CSV"**. O CSV traz o hash gravado no aceite e o
hash atual do documento lado a lado, mais uma coluna `integro` — se algum dia divergirem,
o texto foi alterado depois do aceite.

O próprio usuário consulta os seus aceites em `/legal/meus-aceites/` (LGPD art. 18).

`AceiteLegal` é somente leitura no admin: não há como adicionar, editar ou apagar.

## 2. Publicar uma versão nova das políticas

O **banco é a fonte da verdade**; os arquivos em `legal/documentos/<tipo>/<versao>.md`
são o espelho versionado em git.

1. No admin, em *Documentos legais*, selecione a versão vigente e rode a ação
   **"Duplicar como nova versão (rascunho)"**.
2. Edite o rascunho (Markdown). O campo *Pré-visualização* mostra o resultado
   sanitizado.
3. Decida o campo **mudança material**:
   - marcado → todos terão de aceitar de novo;
   - desmarcado → só correções de redação, sem re-aceite.
4. Selecione o rascunho na lista e rode **"Publicar rascunhos selecionados"**. Isso
   congela o texto, arquiva a versão anterior e, se material, dispara o re-aceite.
5. Espelhe em git:
   ```bash
   ./venv/bin/python manage.py exportar_documentos_legais
   git add legal/documentos && git commit -m "Publica <documento> vX.Y"
   ```

A publicação só existe como **ação da changelist**, nunca como link: ação de admin já vem
como POST com CSRF, enquanto um link mudaria estado por GET.

Uma versão publicada **não** é editável nem apagável pelo admin — nem antes do primeiro
aceite, porque no instante em que ela vai ao ar já está sendo exibida ao público. Para
mudar o texto, publique outra versão.

O caminho inverso (`importar_documentos_legais`) leva ao banco arquivos escritos no
editor. Ele **recusa** sobrescrever uma versão existente cujo texto tenha mudado: é o que
impede alterar retroativamente algo já aceito.

## 3. Guarda dos registros de acesso (6 meses)

O art. 15 do Marco Civil da Internet (Lei 12.965/2014) obriga o provedor de aplicação a
manter os registros de acesso por **6 meses**.

Quem cumpre isso é o nginx, não a aplicação. Instale a rotação deste repositório:

```bash
sudo cp deploy/logrotate/financas-acesso /etc/logrotate.d/financas-acesso
sudo logrotate -d /etc/logrotate.d/financas-acesso   # simulação, não altera nada
```

São 200 rotações diárias — 6 meses com folga. Os logs do gunicorn (journald, 7 dias) são
log de aplicação, não registro de acesso, e não entram nessa conta.

O `X-Forwarded-For` é lido pelo **último** item, em `legal/utils.py:ip_do_request()`.
Atrás do nginx com `proxy_add_x_forwarded_for`, esse é o IP que o nginx observou; os
itens anteriores vieram do cliente e são forjáveis. Usar o primeiro deixaria qualquer um
escolher o IP que ficaria gravado na prova.

## 4. Política de Segurança de Conteúdo no admin

O `/admin/` recebe uma CSP própria, com `'unsafe-eval'`, porque o tema
(django-unfold) usa Alpine.js, que compila as expressões de `x-data`/`x-init` com
`new Function()`. O app público segue com a política estrita. Ver
`core/security_headers.py` e `CONTENT_SECURITY_POLICY_ADMIN` em `config/settings.py`.

## 5. Checklist de deploy

```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py importar_documentos_legais --publicar  # só na 1ª vez
./venv/bin/python manage.py collectstatic --noinput                # unfold traz estáticos
kill -HUP $(cat /run/gunicorn/financas.pid)                        # ou o master do gunicorn
```

`collectstatic` precisa rodar com as variáveis de produção: o app usa
`ManifestStaticFilesStorage`, e um estático fora do manifesto derruba a página com 500.
