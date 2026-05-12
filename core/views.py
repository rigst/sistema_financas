from datetime import timedelta
from decimal import Decimal
import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from core.ai_mentoria import gerar_mentoria_financeira
from financeiro.models import CompartilhamentoDespesa, Despesa, MentoriaFinanceiraIA, ParticipanteCompartilhamentoDespesa, Receita, Reserva, arredondar
from financeiro.planejamento import (
    calcular_planejamento_semanal,
    dados_graficos_dashboard,
    dados_graficos_mensal,
    navegacao_semanal,
    resumo_fluxo_periodo,
    resumo_mensal,
)

logger = logging.getLogger(__name__)


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
    incluir_previstos_mes = request.GET.get("previstos") == "1"
    receitas_qs = Receita.objects.filter(criado_por=request.user, ativa=True)
    despesas_qs = Despesa.objects.filter(criado_por=request.user).exclude(status="cancelada")
    planejamento = calcular_planejamento_semanal(request.user, referencia, quantidade=1, incluir_previstos=incluir_previstos_mes)
    graficos = dados_graficos_dashboard(request.user, referencia)
    mes_resumo = resumo_mensal(request.user, referencia)
    graficos_mes = dados_graficos_mensal(request.user, referencia)
    compartilhadas_pendentes = ParticipanteCompartilhamentoDespesa.objects.filter(usuario=request.user, status="pendente")
    compartilhadas_criadas = CompartilhamentoDespesa.objects.filter(criado_por=request.user)
    compartilhadas_dashboard = {
        "pendentes": compartilhadas_pendentes.count(),
        "valor_pendente": arredondar(sum((item.valor for item in compartilhadas_pendentes), Decimal("0.00"))),
        "criadas": compartilhadas_criadas.count(),
        "aguardando": ParticipanteCompartilhamentoDespesa.objects.filter(
            compartilhamento__criado_por=request.user,
            status="pendente",
        ).count(),
    }

    if periodo != "todos":
        try:
            dias = int(periodo)
        except (TypeError, ValueError):
            dias = 30
        inicio = timezone.localdate() - timedelta(days=dias)
        resumo_periodo = resumo_fluxo_periodo(request.user, inicio, timezone.localdate())
    else:
        inicio = timezone.localdate() - timedelta(days=365 * 5)
        resumo_periodo = resumo_fluxo_periodo(request.user, inicio, timezone.localdate())

    receitas = resumo_periodo["receitas_recebidas"]
    despesas = resumo_periodo["despesas_pagas"]
    pendente_receber = resumo_periodo["receitas_previstas"]
    pendente_pagar = mes_resumo["despesas_pendentes"]

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
        "total_transacoes": len(resumo_periodo["receitas"]) + len(resumo_periodo["despesas"]),
    }

    ultimas_receitas = list(receitas_qs.order_by("-data", "-id")[:5])
    ultimas_despesas = list(despesas_qs.order_by("-data", "-id")[:5])
    def _rotulo_parcela(item):
        if item.tipo != "parcelada":
            return ""
        parcela = item.parcela_na_data(timezone.localdate())
        return f" · {parcela}/{item.parcelas}" if parcela else ""

    ultimos_lancamentos = sorted(
        [
            {
                "tipo": "Receita",
                "data": item.data,
                "descricao": item.descricao,
                "categoria": item.categoria,
                "valor": item.valor,
                "status": f"{item.get_status_display()}{_rotulo_parcela(item)}",
            }
            for item in ultimas_receitas
        ]
        + [
            {
                "tipo": "Despesa",
                "data": item.data,
                "descricao": item.descricao,
                "categoria": item.categoria,
                "valor": item.valor,
                "status": f"{item.get_status_display()}{_rotulo_parcela(item)}",
            }
            for item in ultimas_despesas
        ],
        key=lambda item: item["data"],
        reverse=True,
    )[:5]
    reservas_resumo = [
        {"obj": reserva, "percentual": int(reserva.percentual_concluido)}
        for reserva in Reserva.objects.filter(criado_por=request.user, ativa=True)[:3]
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
        "incluir_previstos_mes": incluir_previstos_mes,
        "mentoria_ia": mentoria_ia,
        "compartilhadas_dashboard": compartilhadas_dashboard,
    }
    return render(request, "core/dashboard.html", context)


@login_required
@require_POST
def gerar_mentoria_ia(request):
    try:
        mentoria = gerar_mentoria_financeira(request.user)
    except (RuntimeError, ValueError) as exc:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "erro": str(exc)}, status=400)
        messages.error(request, str(exc))
    except Exception as exc:
        logger.exception("Erro inesperado ao gerar mentoria financeira da IA")
        mensagem = "Erro inesperado ao gerar a mentoria financeira da IA."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "erro": mensagem}, status=500)
        messages.error(request, mensagem)
    else:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            html = render_to_string("partials/mentoria_ia.html", {"mentoria_ia": mentoria}, request=request)
            return JsonResponse(
                {
                    "ok": True,
                    "html": html,
                    "meta": {
                        "criado_em": timezone.localtime(mentoria.criado_em).strftime("%d/%m/%Y %H:%M"),
                        "periodo_inicio": mentoria.periodo_inicio.strftime("%d/%m/%Y"),
                        "periodo_fim": mentoria.periodo_fim.strftime("%d/%m/%Y"),
                    },
                }
            )
        messages.success(request, "Mentoria financeira da IA atualizada.")
    return redirect("dashboard")


@login_required
def manual(request):
    return render(request, "core/manual.html")
