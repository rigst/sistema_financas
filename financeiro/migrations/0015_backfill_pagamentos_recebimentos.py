import calendar

from django.db import migrations
from django.utils import timezone


def _adicionar_meses(data_base, incremento):
    total = (data_base.year * 12) + (data_base.month - 1) + incremento
    mes = (total % 12) + 1
    ano = total // 12
    dia = min(data_base.day, calendar.monthrange(ano, mes)[1])
    return data_base.replace(year=ano, month=mes, day=dia)


def _meses_entre(inicio, fim):
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month)


def criar_registros(apps, schema_editor):
    """Converte o status único de fixas/parceladas em registros por competência.

    O modelo antigo marcava a série inteira como paga/recebida. Preserva-se
    "pago/recebido" apenas para competências já vencidas (até o mês atual);
    competências futuras voltam a pendente/prevista — comportamento correto
    que o status único mascarava.
    """
    Despesa = apps.get_model("financeiro", "Despesa")
    Receita = apps.get_model("financeiro", "Receita")
    PagamentoDespesa = apps.get_model("financeiro", "PagamentoDespesa")
    RecebimentoReceita = apps.get_model("financeiro", "RecebimentoReceita")

    mes_atual = timezone.localdate().replace(day=1)

    pagamentos = []
    despesas_series = Despesa.objects.filter(tipo__in=["fixa", "parcelada"], status="paga")
    for despesa in despesas_series:
        competencia_base = despesa.competencia.replace(day=1)
        if despesa.tipo == "fixa":
            limite = _meses_entre(competencia_base, mes_atual)
            limite = min(limite, 119)
        else:
            limite = min(_meses_entre(competencia_base, mes_atual), despesa.parcelas - despesa.parcela_atual)
        for incremento in range(0, limite + 1):
            pagamentos.append(
                PagamentoDespesa(
                    despesa=despesa,
                    competencia=_adicionar_meses(competencia_base, incremento),
                    data_pagamento=_adicionar_meses(despesa.data, incremento),
                )
            )
    PagamentoDespesa.objects.bulk_create(pagamentos, ignore_conflicts=True)
    despesas_series.update(status="pendente")

    recebimentos = []
    receitas_series = Receita.objects.filter(tipo__in=["fixa", "parcelada"], status="recebida")
    for receita in receitas_series:
        competencia_base = receita.competencia.replace(day=1)
        if receita.tipo == "fixa":
            limite = _meses_entre(competencia_base, mes_atual)
            limite = min(limite, 119)
        else:
            limite = min(_meses_entre(competencia_base, mes_atual), receita.parcelas - receita.parcela_atual)
        for incremento in range(0, limite + 1):
            recebimentos.append(
                RecebimentoReceita(
                    receita=receita,
                    competencia=_adicionar_meses(competencia_base, incremento),
                    data_recebimento=_adicionar_meses(receita.data, incremento),
                )
            )
    RecebimentoReceita.objects.bulk_create(recebimentos, ignore_conflicts=True)
    receitas_series.update(status="prevista", data_recebimento=None)


def desfazer_registros(apps, schema_editor):
    """Reversão aproximada: restaura o status único a partir dos registros."""
    Despesa = apps.get_model("financeiro", "Despesa")
    Receita = apps.get_model("financeiro", "Receita")
    PagamentoDespesa = apps.get_model("financeiro", "PagamentoDespesa")
    RecebimentoReceita = apps.get_model("financeiro", "RecebimentoReceita")

    despesas_ids = PagamentoDespesa.objects.values_list("despesa_id", flat=True).distinct()
    Despesa.objects.filter(pk__in=list(despesas_ids)).exclude(status="cancelada").update(status="paga")
    receitas_ids = RecebimentoReceita.objects.values_list("receita_id", flat=True).distinct()
    Receita.objects.filter(pk__in=list(receitas_ids)).update(status="recebida")
    PagamentoDespesa.objects.all().delete()
    RecebimentoReceita.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("financeiro", "0014_pagamento_recebimento_por_competencia"),
    ]

    operations = [
        migrations.RunPython(criar_registros, desfazer_registros),
    ]
