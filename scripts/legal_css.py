#!/usr/bin/env python3
"""Escreve o bloco CSS das telas legais em cada app, com a ponte de tokens.

O corpo do bloco é idêntico entre os projetos: ele só usa variáveis
`--legal-*`, definidas na ponte de cada app a partir dos tokens que aquele
app já tem. É o que permite manter as cópias em sincronia sem que o CSS
precise saber se o projeto usa o design system (--ds-*) ou os tokens locais.
"""

from pathlib import Path

MARCA = "/* =========================================================================\n   DOCUMENTOS LEGAIS E ACEITE"

PONTE_DS = """:root {
  --legal-surface: var(--ds-surface);
  --legal-painel: var(--ds-panel);
  --legal-line: var(--ds-line);
  --legal-line-forte: var(--ds-line-strong);
  --legal-t900: var(--ds-t-900);
  --legal-t700: var(--ds-t-700);
  --legal-t500: var(--ds-t-500);
  --legal-accent: var(--ds-accent);
  --legal-accent-forte: var(--ds-accent-dark);
  --legal-danger: var(--ds-danger);
  --legal-warn: var(--ds-warn);
  --legal-raio-lg: var(--ds-radius-lg);
  --legal-raio-md: var(--ds-radius-md);
  --legal-raio-sm: var(--ds-radius-sm);
}"""

PONTE_QUESTOES = """:root {
  --legal-surface: var(--surface);
  --legal-painel: var(--surface-2);
  --legal-line: var(--border);
  --legal-line-forte: var(--border-strong);
  --legal-t900: var(--text);
  --legal-t700: var(--text-soft);
  --legal-t500: var(--muted);
  --legal-accent: var(--accent);
  --legal-accent-forte: var(--accent-strong);
  --legal-danger: var(--danger);
  --legal-warn: var(--warning);
  --legal-raio-lg: var(--radius-lg);
  --legal-raio-md: var(--radius-md);
  --legal-raio-sm: var(--radius-sm);
}"""

PONTE_TRILHAS = """:root {
  --legal-surface: var(--panel);
  --legal-painel: var(--panel-2);
  --legal-line: var(--line);
  --legal-line-forte: var(--line-2);
  --legal-t900: var(--text);
  --legal-t700: var(--muted);
  --legal-t500: var(--dim);
  --legal-accent: var(--teal);
  --legal-accent-forte: var(--teal-2);
  --legal-danger: var(--red);
  --legal-warn: var(--amber);
  --legal-raio-lg: var(--radius);
  --legal-raio-md: var(--radius-sm);
  --legal-raio-sm: var(--radius-xs);
}"""

PONTE_VETORIAL = """:root {
  --legal-surface: var(--surface);
  --legal-painel: var(--surface-2);
  --legal-line: var(--border);
  --legal-line-forte: var(--border-strong);
  --legal-t900: var(--text);
  --legal-t700: var(--text-soft);
  --legal-t500: var(--muted);
  --legal-accent: var(--accent);
  --legal-accent-forte: var(--accent);
  --legal-danger: var(--danger);
  --legal-warn: var(--warning);
  --legal-raio-lg: var(--radius-lg);
  --legal-raio-md: var(--radius-md);
  --legal-raio-sm: var(--radius-sm);
}"""

CORPO = """
.legal-page {
  --legal-medida: 66ch;
  max-width: 52rem;
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
}

.legal-doc {
  background: var(--legal-surface);
  border: 1px solid var(--legal-line);
  border-radius: var(--legal-raio-lg);
  padding: clamp(1.5rem, 5vw, 3rem);
}

/* -- Cabeçalho ----------------------------------------------------------- */

.legal-eyebrow {
  font-size: .75rem;
  font-weight: 600;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--legal-accent-forte);
  margin: 0 0 .5rem;
}

.legal-doc-header h1 {
  margin: 0;
  font-size: clamp(1.75rem, 4vw, 2.25rem);
  line-height: 1.15;
  letter-spacing: -.02em;
}

.legal-lead {
  max-width: var(--legal-medida);
  margin: .875rem 0 0;
  font-size: 1.0625rem;
  line-height: 1.6;
  color: var(--legal-t700);
}

/* Faixa de registro: identidade do documento, em fonte de dados. */
.registro {
  display: flex;
  flex-wrap: wrap;
  gap: .75rem 2rem;
  margin: 1.5rem 0 0;
  padding: .75rem 0 0;
  border-top: 1px solid var(--legal-line);
}

.registro-item { margin: 0; }

.registro dt {
  font-size: .6875rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--legal-t500);
  margin: 0 0 .125rem;
}

.registro dd {
  margin: 0;
  font-size: .875rem;
  font-variant-numeric: tabular-nums;
  color: var(--legal-t900);
}

.registro code {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  font-size: .8125rem;
  color: var(--legal-t700);
  word-break: break-all;
}

/* -- Corpo do documento -------------------------------------------------- */

.legal-corpo {
  counter-reset: clausula;
  max-width: var(--legal-medida);
  margin-top: 2.5rem;
  font-size: 1rem;
  line-height: 1.75;
  color: var(--legal-t700);
}

.legal-corpo > :first-child { margin-top: 0; }
.legal-corpo p { margin: 0 0 1.125rem; }

.legal-corpo h2 {
  counter-increment: clausula;
  position: relative;
  margin: 2.75rem 0 .875rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--legal-line);
  font-size: 1.0625rem;
  line-height: 1.35;
  letter-spacing: -.01em;
  color: var(--legal-t900);
}

/* O número fica pendurado na margem em telas largas e some no mobile, onde
   não há margem sobrando. */
.legal-corpo h2::before {
  content: counter(clausula);
  position: absolute;
  left: -2.75rem;
  top: 1.3rem;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  font-size: .8125rem;
  font-weight: 500;
  color: var(--legal-t500);
}

.legal-corpo h3 {
  margin: 1.75rem 0 .5rem;
  font-size: .9375rem;
  color: var(--legal-t900);
}

.legal-corpo ul,
.legal-corpo ol { margin: 0 0 1.125rem; padding-left: 1.25rem; }
.legal-corpo li { margin-bottom: .5rem; }
.legal-corpo li::marker { color: var(--legal-t500); }
.legal-corpo strong { color: var(--legal-t900); font-weight: 600; }

.legal-corpo table {
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 1.125rem;
  font-size: .9375rem;
}
.legal-corpo th,
.legal-corpo td {
  text-align: left;
  padding: .5rem .75rem;
  border-bottom: 1px solid var(--legal-line);
}

@media (min-width: 60rem) {
  .legal-corpo { margin-left: 2.75rem; }
}

/* -- Aviso de versão arquivada ------------------------------------------- */

.legal-aviso {
  margin: 1.5rem 0 0;
  padding: .75rem 1rem;
  border: 1px solid var(--legal-line);
  border-left: 3px solid var(--legal-warn);
  border-radius: var(--legal-raio-sm);
  background: var(--legal-painel);
  font-size: .9375rem;
  color: var(--legal-t700);
}

/* -- Rodapé do documento ------------------------------------------------- */

.legal-doc-rodape {
  margin-top: 3rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--legal-line);
}

.legal-atalhos {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  font-size: .9375rem;
}

.legal-historico { margin-top: 1.25rem; font-size: .875rem; }
.legal-historico summary {
  cursor: pointer;
  color: var(--legal-t500);
  padding: .25rem 0;
}
.legal-historico ul { margin: .75rem 0 0; padding: 0; list-style: none; }
.legal-historico li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: .5rem 0;
  border-top: 1px solid var(--legal-line);
}
.legal-historico li span { color: var(--legal-t500); }

/* -- Portão de aceite (visitante e re-aceite) ---------------------------- */

.legal-resumo {
  margin: 2rem 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: .75rem;
}

.legal-resumo li {
  max-width: var(--legal-medida);
  padding-left: 1rem;
  border-left: 2px solid var(--legal-accent);
  font-size: .9375rem;
  line-height: 1.6;
  color: var(--legal-t700);
}

.legal-resumo strong { display: block; color: var(--legal-t900); }

/* O texto cortando na borda inferior, sem pista visual, lê-se como conteúdo
   truncado — o degradê e a barra sempre visível são o que dizem "continua". */
.legal-painel {
  position: relative;
  margin-top: 2rem;
  border: 1px solid var(--legal-line);
  border-radius: var(--legal-raio-md);
  overflow: hidden;
}

.legal-painel::after {
  content: "";
  position: absolute;
  left: 1px;
  right: 1px;
  bottom: 1px;
  height: 3rem;
  pointer-events: none;
  background: linear-gradient(to top, var(--legal-surface), transparent);
  border-radius: 0 0 var(--legal-raio-md) var(--legal-raio-md);
}

.legal-painel-topo {
  padding: 1rem 1.25rem;
  background: var(--legal-painel);
  border-bottom: 1px solid var(--legal-line);
}

.legal-painel-topo h2 { margin: 0; font-size: 1rem; }
.legal-painel-topo .registro { margin-top: .625rem; padding-top: .625rem; }

.legal-corpo--rolagem {
  max-width: none;
  margin: 0;
  padding: 1.25rem;
  max-height: 22rem;
  overflow-y: auto;
  font-size: .9375rem;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: var(--legal-line-forte) transparent;
}

.legal-corpo--rolagem::-webkit-scrollbar { width: 10px; }
.legal-corpo--rolagem::-webkit-scrollbar-thumb {
  background: var(--legal-line-forte);
  border: 3px solid var(--legal-surface);
  border-radius: 6px;
}

/* Espaço extra no fim, para a última linha não ficar sob o degradê. */
.legal-corpo--rolagem > :last-child { margin-bottom: 2rem; }

@media (min-width: 60rem) {
  .legal-corpo--rolagem { margin-left: 0; }
}

.legal-corpo--rolagem h2 {
  margin-top: 1.75rem;
  padding-top: .875rem;
  font-size: .9375rem;
}
.legal-corpo--rolagem h2::before { display: none; }
.legal-corpo--rolagem:focus-visible {
  outline: 2px solid var(--legal-accent);
  outline-offset: -2px;
}

/* -- Confirmação --------------------------------------------------------- */

.legal-acao { margin-top: 2rem; }

.confirmacao {
  border: 1px solid var(--legal-line);
  border-radius: var(--legal-raio-md);
  background: var(--legal-painel);
  transition: border-color .15s ease, background-color .15s ease;
}

/* O estado marcado precisa ser visível à distância: é o gesto que vira prova. */
.confirmacao:has(input:checked) {
  border-color: var(--legal-accent);
  background: color-mix(in srgb, var(--legal-accent) 6%, transparent);
}

.confirmacao:has(input:focus-visible) {
  outline: 2px solid var(--legal-accent);
  outline-offset: 2px;
}

.confirmacao-alvo {
  display: flex;
  align-items: flex-start;
  gap: .75rem;
  padding: 1rem 1.25rem;
  cursor: pointer;
}

.confirmacao-alvo input[type="checkbox"] {
  width: 1.125rem;
  height: 1.125rem;
  margin: .125rem 0 0;
  flex: 0 0 auto;
  accent-color: var(--legal-accent);
  cursor: pointer;
}

.confirmacao-texto {
  font-size: .9375rem;
  line-height: 1.55;
  color: var(--legal-t900);
}

.confirmacao--erro { border-color: var(--legal-danger); }
.confirmacao-msg {
  margin: 0;
  padding: 0 1.25rem 1rem;
  font-size: .8125rem;
  color: var(--legal-danger);
}

.legal-acao-botoes {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .75rem;
  margin-top: 1.25rem;
}

.btn-quiet {
  background: none;
  border: 1px solid var(--legal-line);
  color: var(--legal-t700);
}

.legal-recusa { margin-top: 1.5rem; font-size: .875rem; color: var(--legal-t500); }
.legal-recusa p { margin: 0; }

/* Botão que se apresenta como link (recusar sem aceitar). O onclick inline
   seria bloqueado pela CSP, então a recusa é um submit de verdade. */
.link-button {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
}

/* -- Cor de link --------------------------------------------------------
   Onde o app define `a { color: inherit }` num seletor com classe, estes
   precisam de força equivalente para vencer. */

.legal-corpo a,
.legal-atalhos a,
.legal-aviso a,
.legal-historico a,
.confirmacao-texto a,
.legal-page .link-button { color: var(--legal-accent-forte); }

/* Sublinhado, e não só cor. Link dentro de um bloco de texto distinguido
   apenas pela cor reprova o WCAG 1.4.1 (o axe acusa como `link-in-text-block`,
   impacto serious): quem não separa as duas cores não vê que ali há um link.
   Os atalhos e o histórico entram junto porque também vivem em meio a texto
   corrido. */
.legal-corpo a,
.legal-atalhos a,
.legal-aviso a,
.legal-historico a,
.confirmacao-texto a { text-decoration: underline; }

.legal-corpo a:hover,
.legal-atalhos a:hover,
.confirmacao-texto a:hover { color: var(--legal-accent); }

@media (prefers-reduced-motion: reduce) {
  .confirmacao { transition: none; }
}
"""

CABECALHO = """
/* =========================================================================
   DOCUMENTOS LEGAIS E ACEITE (app `legal`)

   O texto vem do banco, renderizado de Markdown: não há classes por elemento,
   então a tipografia é resolvida por seletores de descendência dentro de
   .legal-corpo. Três decisões sustentam a legibilidade:

   1. Medida travada em 66ch. Texto jurídico em linha de 1100px é punitivo.
   2. Seções numeradas por contador CSS. Numeração aqui não é enfeite: cláusula
      de documento legal é citável ("item 3"), e a ordem carrega informação.
   3. Faixa de registro (versão · vigência · impressão do texto). O sha256 é o
      mesmo gravado no aceite — mostrá-lo é o que deixa a prova verificável.

   O corpo abaixo é idêntico entre os projetos: só usa variáveis --legal-*,
   definidas na ponte logo a seguir a partir dos tokens de cada app.
   ========================================================================= */

"""

APPS = {
    "/var/www/sistema_financas/current/static/css/style.css": PONTE_DS,
    "/var/www/sistema_orcamentos/current/static/css/style.css": PONTE_DS,
    "/var/www/divisor_pdf/static/css/style.css": PONTE_DS,
    "/var/www/sistema_questoes/current/static/css/questoes.css": PONTE_QUESTOES,
    "/var/www/sistema_trilhas/static/css/app.css": PONTE_TRILHAS,
    "/var/www/sistema_vetorial/current/static/css/style.css": PONTE_VETORIAL,
}


def main():
    for caminho, ponte in APPS.items():
        p = Path(caminho)
        t = p.read_text(encoding="utf-8")
        for antiga in (
            MARCA,
            "/* =========================================================================\n   PÁGINAS LEGAIS E ACEITE",
        ):
            if antiga in t:
                t = t[: t.index(antiga)].rstrip() + "\n"
        p.write_text(t + CABECALHO + ponte + "\n" + CORPO, encoding="utf-8")
        print(f"  {caminho}: {p.read_text(encoding='utf-8').count(chr(10))} linhas")


if __name__ == "__main__":
    main()
