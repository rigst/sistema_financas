# Fontes

Todas auto-hospedadas: **nenhuma requisição sai para o Google**. É requisito de
LGPD do projeto — o CDN de fontes registra o IP de cada visitante.

Os arquivos foram obtidos da API do Google Fonts e recortados nos subconjuntos
`latin` e `latin-ext`, que é o que o português precisa.

| Família | Arquivos | Eixos | Uso no sistema |
|---|---|---|---|
| **Archivo** | `archivo-var-latin*.woff2` | `wght 100–900`, `wdth 62–125` | `--ds-font-display` — títulos |
| **IBM Plex Sans** | `ibm-plex-sans-var-latin*.woff2` | `wght 100–700` | `--ds-font-sans` — corpo |
| **IBM Plex Mono** | `ibm-plex-mono-{400,500,600}-latin*.woff2` | estático | `--ds-font-mono` — rótulo e número |

O eixo `wdth` do Archivo é usado de verdade (`wdth 106` a `118` conforme o
nível do título). Substituir por um Archivo só de peso achata a tipografia
inteira do sistema.

## Licença

As três estão sob a **SIL Open Font License 1.1**, que permite uso, modificação
e redistribuição, inclusive comercial e embarcada em página web. O texto
completo está em `OFL-archivo.txt`.

- Archivo — Copyright (c) Omnibus-Type. <https://github.com/Omnibus-Type/Archivo>
- IBM Plex Sans / IBM Plex Mono — Copyright (c) IBM Corp.
  <https://github.com/IBM/plex>

A OFL exige que o aviso de copyright e a própria licença acompanhem os
arquivos. É o que este documento faz — **não remover ao copiar a pasta para um
app.**
