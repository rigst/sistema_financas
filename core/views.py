from datetime import timedelta
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.tenancy import definir_empresa_ativa, queryset_da_empresa
from orcamentos.models import Orcamento


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
    ultimos_orcamentos = queryset_da_empresa(
        Orcamento.objects.select_related("cliente")
        .filter(ativo=True)
        .exclude(status__in=["rejeitado", "cancelado"])
        .order_by("-criado_em"),
        request.user,
    )
    orcamentos = queryset_da_empresa(Orcamento.objects.filter(ativo=True), request.user)

    if periodo != "todos":
        try:
            dias = int(periodo)
        except (TypeError, ValueError):
            dias = 30
        from django.utils import timezone

        inicio = timezone.localdate() - timedelta(days=dias)
        orcamentos = orcamentos.filter(data_emissao__gte=inicio)
        ultimos_orcamentos = ultimos_orcamentos.filter(data_emissao__gte=inicio)

    resumo_status = (
        orcamentos.values("status")
        .annotate(total=Count("id"))
    )

    status_map = {
        "rascunho": 0,
        "em_elaboracao": 0,
        "enviado": 0,
        "aprovado": 0,
    }

    for item in resumo_status:
        if item["status"] in status_map:
            status_map[item["status"]] = item["total"]

    indicadores = orcamentos.aggregate(
        total_orcamentos=Count("id"),
        valor_total=Coalesce(Sum("total_final"), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2)),
    )
    indicadores["valor_aprovado"] = orcamentos.filter(status="aprovado").aggregate(
        total=Coalesce(Sum("total_final"), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2))
    )["total"]
    indicadores["pendentes"] = orcamentos.filter(status__in=["rascunho", "em_elaboracao", "enviado"]).count()
    ultimos_orcamentos = ultimos_orcamentos[:5]

    context = {
        "ultimos_orcamentos": ultimos_orcamentos,
        "status_map": status_map,
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
            "descricao": "Acompanha o sistema inteiro e gerencia clientes, catálogo, empresa, orçamentos e usuários.",
        },
        {
            "nome": "Orçamentista",
            "descricao": "Trabalha com clientes e orçamentos, consulta catálogo e empresa, e acompanha relatórios.",
        },
        {
            "nome": "Visualizador",
            "descricao": "Consulta informações do sistema sem editar cadastros nem movimentar orçamentos.",
        },
    ]
    return render(
        request,
        "core/manual.html",
        {
            "perfis_manual": perfis,
        },
    )


@login_required
@require_POST
def alternar_empresa(request):
    empresa_id = request.POST.get("empresa_id")
    empresa = definir_empresa_ativa(request, request.user, empresa_id)

    if empresa is None:
        messages.error(request, "Empresa inválida para este usuário.")
    else:
        messages.success(request, f"Empresa ativa alterada para {empresa.nome}.")

    destino = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("dashboard")
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        destino = reverse("dashboard")
    return redirect(destino)
