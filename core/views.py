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
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.tenancy import definir_empresa_ativa, queryset_da_empresa
from financeiro.models import Conta, FaturaCartao, Transacao, arredondar


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
    contas = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), request.user)
    transacoes = queryset_da_empresa(
        Transacao.objects.select_related("conta", "conta_destino", "categoria").exclude(status="cancelado"),
        request.user,
    )

    if periodo != "todos":
        try:
            dias = int(periodo)
        except (TypeError, ValueError):
            dias = 30
        inicio = timezone.localdate() - timedelta(days=dias)
        transacoes_periodo = transacoes.filter(data_competencia__gte=inicio)
    else:
        transacoes_periodo = transacoes

    soma_field = DecimalField(max_digits=14, decimal_places=2)
    receitas = transacoes_periodo.filter(tipo="receita", status="pago").aggregate(
        total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)
    )["total"]
    despesas = transacoes_periodo.filter(tipo="despesa", status="pago").aggregate(
        total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)
    )["total"]
    pendente_receber = transacoes.filter(tipo="receita", status="pendente").aggregate(
        total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)
    )["total"]
    pendente_pagar = transacoes.filter(tipo="despesa", status="pendente").aggregate(
        total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)
    )["total"]

    contas_lista = list(contas)
    saldo_total = arredondar(sum((conta.saldo_atual() for conta in contas_lista), Decimal("0.00")))
    indicadores = {
        "saldo_total": saldo_total,
        "receitas": arredondar(receitas),
        "despesas": arredondar(despesas),
        "resultado": arredondar(receitas - despesas),
        "pendente_receber": arredondar(pendente_receber),
        "pendente_pagar": arredondar(pendente_pagar),
        "total_contas": len(contas_lista),
        "total_transacoes": transacoes_periodo.count(),
    }

    categorias_despesa = (
        transacoes_periodo.filter(tipo="despesa", status="pago", categoria__isnull=False)
        .values("categoria__nome", "categoria__cor")
        .annotate(total=Coalesce(Sum("valor"), Value(0), output_field=soma_field))
        .order_by("-total")[:5]
    )
    ultimas_transacoes = transacoes.order_by("-data_competencia", "-id")[:8]
    faturas_abertas = queryset_da_empresa(
        FaturaCartao.objects.select_related("cartao").filter(status__in=["aberta", "fechada"]),
        request.user,
    ).order_by("data_vencimento", "ano", "mes")[:6]

    context = {
        "contas": contas_lista,
        "categorias_despesa": categorias_despesa,
        "ultimas_transacoes": ultimas_transacoes,
        "faturas_abertas": faturas_abertas,
        "indicadores": indicadores,
        "periodo": periodo,
        "saudacao_dashboard": f"Bom ter você por aqui, {request.user}.",
    }
    return render(request, "core/dashboard.html", context)


@login_required
def manual(request):
    perfis = [
        {
            "nome": "Administrador",
            "descricao": "Acompanha o sistema inteiro e gerencia finanças, configurações e usuários.",
        },
        {
            "nome": "Editor",
            "descricao": "Registra contas, categorias e transações financeiras.",
        },
        {
            "nome": "Visualizador",
            "descricao": "Consulta informações financeiras sem editar cadastros nem lançamentos.",
        },
    ]
    return render(request, "core/manual.html", {"perfis_manual": perfis})


@login_required
@require_POST
def alternar_empresa(request):
    empresa_id = request.POST.get("empresa_id")
    empresa = definir_empresa_ativa(request, request.user, empresa_id)

    if empresa is None:
        messages.error(request, "Espaço financeiro inválido para este usuário.")
    else:
        messages.success(request, f"Espaço financeiro ativo alterado para {empresa.nome}.")

    destino = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("dashboard")
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        destino = reverse("dashboard")
    return redirect(destino)
