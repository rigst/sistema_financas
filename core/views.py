from datetime import timedelta
from decimal import Decimal
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from core.ai_mentoria import gerar_mentoria_financeira
from financeiro.models import Despesa, MentoriaFinanceiraIA, Receita, Reserva, arredondar
from financeiro.planejamento import (
    calcular_planejamento_semanal,
    dados_graficos_dashboard,
    dados_graficos_mensal,
    navegacao_semanal,
    resumo_mensal,
)


def healthz(request):
    healthz_token = getattr(settings, "HEALTHZ_TOKEN", "")
    if healthz_token:
        token_recebido = request.headers.get("X-Healthz-Token", "").strip()
        if not token_recebido or not secrets.compare_digest(token_recebido, healthz_token):
            return HttpResponseNotFound()
    return JsonResponse({"status": "ok"})


@login_required
def dashboard(request):
    periodo = request.GET.get("periodo", "30")
    referencia = parse_date(request.GET.get("semana", "")) or timezone.localdate()
    receitas_qs = Receita.objects.filter(criado_por=request.user)
    despesas_qs = Despesa.objects.filter(criado_por=request.user).exclude(status="cancelada")
    planejamento = calcular_planejamento_semanal(request.user, referencia, quantidade=1)
    graficos = dados_graficos_dashboard(request.user, referencia)
    mes_resumo = resumo_mensal(request.user, referencia)
    graficos_mes = dados_graficos_mensal(request.user, referencia)

    if periodo != "todos":
        try:
            dias = int(periodo)
        except (TypeError, ValueError):
            dias = 30
        inicio = timezone.localdate() - timedelta(days=dias)
        receitas_periodo = receitas_qs.filter(data__gte=inicio)
        despesas_periodo = despesas_qs.filter(data__gte=inicio)
    else:
        receitas_periodo = receitas_qs
        despesas_periodo = despesas_qs

    soma_field = DecimalField(max_digits=14, decimal_places=2)
    receitas = receitas_periodo.filter(status="recebida").aggregate(
        total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)
    )["total"]
    despesas = despesas_periodo.filter(status="paga").aggregate(
        total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)
    )["total"]
    pendente_receber = receitas_qs.filter(status="prevista").aggregate(
        total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)
    )["total"]
    pendente_pagar = despesas_qs.filter(status="pendente").aggregate(
        total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)
    )["total"]

    indicadores = {
        "saldo_total": planejamento["saldo_total"],
        "disponivel_semana": planejamento["semana_atual"]["disponivel"] if planejamento["semana_atual"] else Decimal("0.00"),
        "cota_semana": planejamento["semana_atual"]["cota_semana"] if planejamento["semana_atual"] else Decimal("0.00"),
        "gasto_semana": planejamento["semana_atual"]["gasto_semana"] if planejamento["semana_atual"] else Decimal("0.00"),
        "compromissos": planejamento["total_comprometido"],
        "disponivel_apos_compromissos": planejamento["disponivel_apos_compromissos"],
        "receitas": arredondar(receitas),
        "despesas": arredondar(despesas),
        "resultado": arredondar(receitas - despesas),
        "pendente_receber": arredondar(pendente_receber),
        "pendente_pagar": arredondar(pendente_pagar),
        "total_contas": 0,
        "total_transacoes": receitas_periodo.count() + despesas_periodo.count(),
    }

    ultimas_receitas = list(receitas_qs.order_by("-data", "-id")[:5])
    ultimas_despesas = list(despesas_qs.order_by("-data", "-id")[:5])
    ultimos_lancamentos = sorted(
        [{"tipo": "Receita", "data": item.data, "descricao": item.descricao, "valor": item.valor, "status": item.get_status_display()} for item in ultimas_receitas]
        + [{"tipo": "Despesa", "data": item.data, "descricao": item.descricao, "valor": item.valor, "status": item.get_status_display()} for item in ultimas_despesas],
        key=lambda item: item["data"],
        reverse=True,
    )[:5]
    reservas_resumo = [
        {"obj": reserva, "percentual": int(reserva.percentual_concluido)}
        for reserva in Reserva.objects.filter(criado_por=request.user)[:3]
    ]
    mentoria_ia = MentoriaFinanceiraIA.objects.filter(criado_por=request.user).first()

    context = {
        "planejamento_semanal": planejamento["semanas"],
        "ultimos_lancamentos": ultimos_lancamentos,
        "reservas_resumo": reservas_resumo,
        "graficos": graficos,
        "graficos_mes": graficos_mes,
        "indicadores": indicadores,
        "mes_resumo": mes_resumo,
        "periodo": periodo,
        "semana_nav": navegacao_semanal(referencia),
        "mentoria_ia": mentoria_ia,
    }
    return render(request, "core/dashboard.html", context)


@login_required
@require_POST
def gerar_mentoria_ia(request):
    try:
        gerar_mentoria_financeira(request.user)
    except (RuntimeError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Mentoria financeira da IA atualizada.")
    return redirect("dashboard")


@login_required
def manual(request):
    return render(request, "core/manual.html")
