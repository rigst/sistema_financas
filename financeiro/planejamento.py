from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from core.tenancy import queryset_da_empresa
from .models import Despesa, Receita, arredondar

SOMA_DECIMAL = DecimalField(max_digits=14, decimal_places=2)


def inicio_da_semana(data_base):
    return data_base - timedelta(days=data_base.weekday())


def fim_da_semana(data_base):
    return inicio_da_semana(data_base) + timedelta(days=6)


def navegacao_semanal(referencia):
    inicio = inicio_da_semana(referencia)
    return {
        "referencia": referencia,
        "inicio": inicio,
        "fim": inicio + timedelta(days=6),
        "anterior": inicio - timedelta(days=7),
        "proxima": inicio + timedelta(days=7),
    }


def _somar(queryset, campo="valor"):
    return arredondar(queryset.aggregate(total=Coalesce(Sum(campo), Value(0), output_field=SOMA_DECIMAL))["total"])


def _despesas_no_periodo(user, inicio, fim):
    despesas = queryset_da_empresa(Despesa.objects.exclude(status="cancelada"), user)
    ocorrencias = []
    for despesa in despesas:
        for ocorrencia in despesa.ocorrencias(inicio, fim):
            ocorrencias.append({"despesa": despesa, **ocorrencia})
    return ocorrencias


def calcular_planejamento_semanal(user, referencia, quantidade=5):
    receitas = queryset_da_empresa(Receita.objects.all(), user)
    despesas = queryset_da_empresa(Despesa.objects.exclude(status="cancelada"), user)
    saldo_total = arredondar(_somar(receitas.filter(status="recebida")) - _somar(despesas.filter(status="paga")))
    primeira_semana = inicio_da_semana(referencia)
    saldo_projetado = saldo_total
    semanas = []

    for indice in range(quantidade):
        inicio = primeira_semana + timedelta(days=7 * indice)
        fim = inicio + timedelta(days=6)
        receitas_semana = receitas.filter(data__range=(inicio, fim))
        entradas_previstas = _somar(receitas_semana.filter(status="prevista"))
        entradas_recebidas = _somar(receitas_semana.filter(status="recebida"))
        ocorrencias = _despesas_no_periodo(user, inicio, fim)
        gastos_pagos = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].status == "paga"), Decimal("0.00")))
        fixos = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "fixa" and item["despesa"].status != "paga"), Decimal("0.00")))
        parcelas = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "parcelada" and item["despesa"].status != "paga"), Decimal("0.00")))
        variaveis_pendentes = arredondar(sum((item["valor"] for item in ocorrencias if item["despesa"].tipo == "variavel" and item["despesa"].status == "pendente"), Decimal("0.00")))
        compromissos = arredondar(fixos + parcelas + variaveis_pendentes)
        saldo_projetado = arredondar(saldo_projetado + entradas_previstas - compromissos)
        semanas.append(
            {
                "inicio": inicio,
                "fim": fim,
                "rotulo": f"{inicio:%d/%m} a {fim:%d/%m}",
                "semana_atual": inicio <= referencia <= fim,
                "receitas": arredondar(entradas_previstas + entradas_recebidas),
                "receitas_previstas": entradas_previstas,
                "receitas_recebidas": entradas_recebidas,
                "gastos_pagos": gastos_pagos,
                "gastos_pendentes": variaveis_pendentes,
                "fixos": fixos,
                "parcelas": parcelas,
                "compromissos": compromissos,
                "gasto_total": arredondar(gastos_pagos + compromissos),
                "disponivel": saldo_projetado,
            }
        )

    semana_atual = semanas[0] if semanas else None
    total_comprometido = arredondar(sum((semana["compromissos"] for semana in semanas), Decimal("0.00")))
    disponivel_apos_compromissos = arredondar(saldo_total - total_comprometido)
    return {
        "saldo_total": saldo_total,
        "semanas": semanas,
        "semana_atual": semana_atual,
        "total_comprometido": total_comprometido,
        "disponivel_apos_compromissos": disponivel_apos_compromissos,
    }


def dados_graficos_dashboard(user, referencia):
    inicio = inicio_da_semana(referencia)
    fim = inicio + timedelta(days=6)
    despesas_semana = _despesas_no_periodo(user, inicio, fim)
    por_tipo = {"Variáveis": Decimal("0.00"), "Fixas": Decimal("0.00"), "Parceladas": Decimal("0.00")}
    por_categoria = {}
    for item in despesas_semana:
        despesa = item["despesa"]
        valor = item["valor"]
        if despesa.tipo == "fixa":
            por_tipo["Fixas"] += valor
        elif despesa.tipo == "parcelada":
            por_tipo["Parceladas"] += valor
        else:
            por_tipo["Variáveis"] += valor
        categoria = despesa.categoria or "Sem categoria"
        por_categoria[categoria] = por_categoria.get(categoria, Decimal("0.00")) + valor
    maior_categoria = max(por_categoria.values(), default=Decimal("0.00")) or Decimal("1.00")
    return {
        "por_tipo": [{"label": chave, "valor": arredondar(valor)} for chave, valor in por_tipo.items()],
        "por_categoria": [
            {"label": chave, "valor": arredondar(valor), "percentual": int((valor / maior_categoria) * Decimal("100"))}
            for chave, valor in sorted(por_categoria.items(), key=lambda item: item[1], reverse=True)[:6]
        ],
    }
