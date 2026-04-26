from django import template
from django.utils.text import slugify

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


@register.filter
def categoria_icone(categoria):
    texto = slugify(str(categoria or ""))
    grupos = [
        (("casa", "moradia", "aluguel", "condominio"), "home"),
        (("mercado", "supermercado", "compra", "compras", "shopping"), "cart"),
        (("alimentacao", "restaurante", "comida", "lanche", "padaria"), "utensils"),
        (("transporte", "carro", "combustivel", "uber", "onibus"), "car"),
        (("saude", "medico", "farmacia", "remedio"), "health"),
        (("educacao", "curso", "escola", "faculdade", "livro"), "education"),
        (("trabalho", "servico", "servicos", "freelance"), "work"),
        (("lazer", "viagem", "cinema", "presente"), "star"),
        (("conta", "contas", "luz", "agua", "internet", "telefone"), "receipt"),
        (("salario", "receita", "venda", "reembolso"), "money"),
    ]
    for termos, icone in grupos:
        if any(termo in texto for termo in termos):
            return icone
    return "tag"
