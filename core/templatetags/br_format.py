from django import template

from core.formatting import formatar_decimal_br, formatar_moeda_br

register = template.Library()


@register.filter
def brl(valor):
    return formatar_moeda_br(valor)


@register.filter
def decimal_br(valor, casas=2):
    try:
        casas_int = int(casas)
    except (TypeError, ValueError):
        casas_int = 2
    return formatar_decimal_br(valor, casas=casas_int)


@register.filter
def percentual_br(valor, casas=2):
    return f"{decimal_br(valor, casas)}%"
