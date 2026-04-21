import re

from django import template
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()

ITEM_RE = re.compile(r"^\s*(?:[-*•]|\d+[\.\)])\s+")


@register.filter(needs_autoescape=True)
def mentoria_formatada(valor, autoescape=True):
    if not valor:
        return ""

    escape = conditional_escape if autoescape else lambda item: item
    paragrafos = []
    itens = []

    for linha in str(valor).splitlines():
        texto = linha.strip()
        if not texto:
            continue
        if ITEM_RE.match(texto):
            itens.append(ITEM_RE.sub("", texto).strip())
        else:
            paragrafos.append(texto)

    blocos = []
    if paragrafos:
        blocos.append(
            format_html(
                '<div class="ai-mentor-summary">{}</div>',
                format_html_join("", "<p>{}</p>", ((escape(paragrafo),) for paragrafo in paragrafos)),
            )
        )
    if itens:
        blocos.append(
            format_html(
                '<ol class="ai-mentor-list">{}</ol>',
                format_html_join("", "<li><span>{}</span></li>", ((escape(item),) for item in itens)),
            )
        )
    if not blocos:
        blocos.append(format_html('<div class="ai-mentor-summary"><p>{}</p></div>', escape(valor)))

    return mark_safe("".join(str(bloco) for bloco in blocos))
