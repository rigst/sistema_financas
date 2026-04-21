import csv
from decimal import Decimal

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required
from core.query import paginate_queryset
from core.search import filter_ranked_search
from .forms import DespesaSimplificadaForm, ReceitaSimplificadaForm, ReservaForm
from .models import Despesa, Receita, Reserva, arredondar
from .planejamento import calcular_planejamento_semanal, navegacao_semanal


def _queryset_simples(modelo, request):
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    itens = modelo.objects.filter(criado_por=request.user)
    status_validos = {choice[0] for choice in modelo.STATUS_CHOICES}
    if status in status_validos:
        itens = itens.filter(status=status)
    if busca:
        itens = filter_ranked_search(itens, busca, ("descricao", "observacoes", "categoria"))
    return itens, busca, status


def _voltar_para(request, fallback):
    destino = request.POST.get("next") or request.GET.get("next") or reverse(fallback)
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(fallback)


def _referencia_semanal(request):
    return parse_date(request.GET.get("semana", "")) or timezone.localdate()


@login_required
def receita_lista(request):
    receitas, busca, status = _queryset_simples(Receita, request)
    page_obj = paginate_queryset(request, receitas, per_page=25)
    return render(
        request,
        "financeiro/receita_lista.html",
        {"receitas": page_obj, "page_obj": page_obj, "busca": busca, "status": status},
    )


@login_required
def receita_criar(request):
    if request.method == "POST":
        form = ReceitaSimplificadaForm(request.POST, user=request.user)
        if form.is_valid():
            receita = form.save(commit=False)
            receita.criado_por = request.user
            receita.save()
            messages.success(request, "Receita salva com sucesso.")
            return redirect("financeiro:receita_lista")
    else:
        form = ReceitaSimplificadaForm(user=request.user)
    return render(request, "financeiro/receita_form.html", {"form": form, "titulo": "Nova receita"})


@login_required
def receita_editar(request, pk):
    receita = get_object_or_404(Receita.objects.filter(criado_por=request.user), pk=pk)
    if request.method == "POST":
        form = ReceitaSimplificadaForm(request.POST, instance=receita, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Receita atualizada com sucesso.")
            return redirect("financeiro:receita_lista")
    else:
        form = ReceitaSimplificadaForm(instance=receita, user=request.user)
    return render(request, "financeiro/receita_form.html", {"form": form, "titulo": "Editar receita"})


@require_POST
@login_required
def receita_marcar_recebida(request, pk):
    receita = get_object_or_404(Receita.objects.filter(criado_por=request.user), pk=pk)
    receita.status = "recebida"
    receita.save(update_fields=["status", "atualizado_em"])
    messages.success(request, "Receita marcada como recebida.")
    return _voltar_para(request, "financeiro:receita_lista")


@login_required
def despesa_lista(request):
    despesas, busca, status = _queryset_simples(Despesa, request)
    tipo = request.GET.get("tipo", "").strip()
    tipos_validos = {choice[0] for choice in Despesa.TIPO_CHOICES}
    if tipo in tipos_validos:
        despesas = despesas.filter(tipo=tipo)
    fixas = Despesa.objects.filter(criado_por=request.user, tipo="fixa").exclude(status="cancelada").order_by("descricao")
    page_obj = paginate_queryset(request, despesas, per_page=25)
    return render(
        request,
        "financeiro/despesa_lista.html",
        {
            "despesas": page_obj,
            "page_obj": page_obj,
            "busca": busca,
            "status": status,
            "tipo": tipo,
            "fixas": fixas,
        },
    )


@login_required
def despesa_criar(request):
    if request.method == "POST":
        form = DespesaSimplificadaForm(request.POST, user=request.user)
        if form.is_valid():
            despesa = form.save(commit=False)
            despesa.criado_por = request.user
            despesa.save()
            messages.success(request, "Despesa salva com sucesso.")
            return redirect("financeiro:despesa_lista")
    else:
        form = DespesaSimplificadaForm(user=request.user)
    return render(request, "financeiro/despesa_form.html", {"form": form, "titulo": "Nova despesa"})


@login_required
def despesa_editar(request, pk):
    despesa = get_object_or_404(Despesa.objects.filter(criado_por=request.user), pk=pk)
    if request.method == "POST":
        form = DespesaSimplificadaForm(request.POST, instance=despesa, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Despesa atualizada com sucesso.")
            return redirect("financeiro:despesa_lista")
    else:
        form = DespesaSimplificadaForm(instance=despesa, user=request.user)
    return render(request, "financeiro/despesa_form.html", {"form": form, "titulo": "Editar despesa"})


@require_POST
@login_required
def despesa_marcar_paga(request, pk):
    despesa = get_object_or_404(Despesa.objects.filter(criado_por=request.user).exclude(status="cancelada"), pk=pk)
    despesa.status = "paga"
    despesa.save(update_fields=["status", "atualizado_em"])
    messages.success(request, "Despesa marcada como paga.")
    return _voltar_para(request, "financeiro:despesa_lista")


@require_POST
@login_required
def despesa_cancelar(request, pk):
    despesa = get_object_or_404(Despesa.objects.filter(criado_por=request.user), pk=pk)
    despesa.status = "cancelada"
    despesa.save(update_fields=["status", "atualizado_em"])
    messages.success(request, "Despesa cancelada.")
    return _voltar_para(request, "financeiro:despesa_lista")


@login_required
def exportar_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="financeiro_simplificado.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["tipo", "descricao", "valor", "data", "categoria", "status", "parcelas", "observacoes"])

    receitas = Receita.objects.filter(criado_por=request.user).order_by("data", "id")
    despesas = Despesa.objects.filter(criado_por=request.user).order_by("data", "id")
    for item in receitas:
        writer.writerow(["receita", item.descricao, item.valor, item.data.isoformat(), item.categoria, item.get_status_display(), "", item.observacoes])
    for item in despesas:
        writer.writerow(["despesa", item.descricao, item.valor, item.data.isoformat(), item.categoria, item.get_status_display(), item.parcelas, item.observacoes])
    return response


@login_required
def controle(request):
    referencia = _referencia_semanal(request)
    planejamento = calcular_planejamento_semanal(request.user, referencia, quantidade=6)
    reservas = Reserva.objects.filter(criado_por=request.user)
    fixas = Despesa.objects.filter(criado_por=request.user, tipo="fixa").exclude(status="cancelada").order_by("descricao")
    reservas_total = arredondar(sum((reserva.valor_atual for reserva in reservas), Decimal("0.00")))
    return render(
        request,
        "financeiro/controle.html",
        {
            "planejamento": planejamento,
            "reservas": reservas,
            "fixas": fixas,
            "reservas_total": reservas_total,
            "semana_nav": navegacao_semanal(referencia),
        },
    )


@login_required
def reserva_criar(request):
    if request.method == "POST":
        form = ReservaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.criado_por = request.user
            reserva.save()
            messages.success(request, "Reserva salva com sucesso.")
            return redirect("financeiro:controle")
    else:
        form = ReservaForm()
    return render(request, "financeiro/reserva_form.html", {"form": form, "titulo": "Nova reserva"})


@login_required
def reserva_editar(request, pk):
    reserva = get_object_or_404(Reserva.objects.filter(criado_por=request.user), pk=pk)
    if request.method == "POST":
        form = ReservaForm(request.POST, instance=reserva)
        if form.is_valid():
            form.save()
            messages.success(request, "Reserva atualizada com sucesso.")
            return redirect("financeiro:controle")
    else:
        form = ReservaForm(instance=reserva)
    return render(request, "financeiro/reserva_form.html", {"form": form, "titulo": "Editar reserva"})
