from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import require_capability
from core.query import paginate_queryset
from core.search import filter_ranked_search
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from .forms import CategoriaFinanceiraForm, ContaForm, TransacaoForm
from .models import CategoriaFinanceira, Conta, Transacao


@require_capability("pode_visualizar_financeiro")
def conta_lista(request):
    busca = request.GET.get("q", "").strip()
    ativo = request.GET.get("ativo", "ativas").strip()
    ordenar = request.GET.get("sort", "nome")
    contas = queryset_da_empresa(Conta.objects.all(), request.user)
    contas = contas.filter(ativa=(ativo != "inativas"))
    ordenacoes = {
        "nome": "nome",
        "tipo": "tipo",
        "instituicao": "instituicao",
        "recentes": "-atualizado_em",
    }
    contas = contas.order_by(ordenacoes.get(ordenar, "nome"))
    if busca:
        contas = filter_ranked_search(contas, busca, ("nome", "instituicao"))
    page_obj = paginate_queryset(request, contas, per_page=20)
    return render(request, "financeiro/conta_lista.html", {"contas": page_obj, "page_obj": page_obj, "busca": busca, "ativo": ativo, "sort": ordenar})


@require_capability("pode_gerenciar_financeiro")
def conta_criar(request):
    if request.method == "POST":
        form = ContaForm(request.POST)
        if form.is_valid():
            conta = form.save(commit=False)
            conta.empresa = obter_grupo_empresa_ou_erro(request.user)
            conta.save()
            messages.success(request, "Conta criada com sucesso.")
            return redirect("financeiro:conta_lista")
    else:
        form = ContaForm()
    return render(request, "financeiro/conta_form.html", {"form": form, "titulo": "Nova conta"})


@require_capability("pode_visualizar_financeiro")
def conta_visualizar(request, pk):
    conta = get_object_or_404(queryset_da_empresa(Conta.objects.all(), request.user), pk=pk)
    form = ContaForm(instance=conta)
    return render(request, "financeiro/conta_form.html", {"form": form, "titulo": "Conta", "conta": conta, "somente_leitura": True})


@require_capability("pode_gerenciar_financeiro")
def conta_editar(request, pk):
    conta = get_object_or_404(queryset_da_empresa(Conta.objects.all(), request.user), pk=pk)
    if request.method == "POST":
        form = ContaForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta atualizada com sucesso.")
            return redirect("financeiro:conta_lista")
    else:
        form = ContaForm(instance=conta)
    return render(request, "financeiro/conta_form.html", {"form": form, "titulo": "Editar conta", "conta": conta})


@require_capability("pode_gerenciar_financeiro")
def conta_excluir(request, pk):
    conta = get_object_or_404(queryset_da_empresa(Conta.objects.all(), request.user), pk=pk)
    acao = "reativar" if not conta.ativa else "inativar"
    if request.method == "POST":
        conta.ativa = not conta.ativa
        conta.save(update_fields=["ativa", "atualizado_em"])
        messages.success(request, "Conta reativada com sucesso." if conta.ativa else "Conta inativada com sucesso.")
        return redirect("financeiro:conta_lista")
    return render(request, "financeiro/confirmar_status.html", {"objeto": conta, "tipo": "conta", "acao": acao, "voltar_url": "financeiro:conta_lista"})


@require_capability("pode_visualizar_financeiro")
def conta_extrato(request, pk):
    conta = get_object_or_404(queryset_da_empresa(Conta.objects.all(), request.user), pk=pk)
    transacoes = queryset_da_empresa(Transacao.objects.select_related("conta", "conta_destino", "categoria"), request.user).filter(
        Q(conta=conta) | Q(conta_destino=conta)
    ).order_by("-data_competencia", "-id")
    page_obj = paginate_queryset(request, transacoes, per_page=30)
    return render(request, "financeiro/conta_extrato.html", {"conta": conta, "transacoes": page_obj, "page_obj": page_obj})


@require_capability("pode_visualizar_financeiro")
def categoria_lista(request):
    busca = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    ativo = request.GET.get("ativo", "ativas").strip()
    ordenar = request.GET.get("sort", "nome")
    categorias = queryset_da_empresa(CategoriaFinanceira.objects.select_related("categoria_pai"), request.user)
    categorias = categorias.filter(ativa=(ativo != "inativas"))
    if tipo in {"receita", "despesa"}:
        categorias = categorias.filter(tipo=tipo)
    ordenacoes = {"nome": "nome", "tipo": "tipo", "recentes": "-atualizado_em"}
    categorias = categorias.order_by(ordenacoes.get(ordenar, "nome"))
    if busca:
        categorias = filter_ranked_search(categorias, busca, ("nome", "categoria_pai__nome"))
    page_obj = paginate_queryset(request, categorias, per_page=20)
    return render(request, "financeiro/categoria_lista.html", {"categorias": page_obj, "page_obj": page_obj, "busca": busca, "tipo": tipo, "ativo": ativo, "sort": ordenar})


@require_capability("pode_gerenciar_financeiro")
def categoria_criar(request):
    if request.method == "POST":
        form = CategoriaFinanceiraForm(request.POST, user=request.user)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.empresa = obter_grupo_empresa_ou_erro(request.user)
            categoria.save()
            messages.success(request, "Categoria criada com sucesso.")
            return redirect("financeiro:categoria_lista")
    else:
        form = CategoriaFinanceiraForm(user=request.user)
    return render(request, "financeiro/categoria_form.html", {"form": form, "titulo": "Nova categoria"})


@require_capability("pode_visualizar_financeiro")
def categoria_visualizar(request, pk):
    categoria = get_object_or_404(queryset_da_empresa(CategoriaFinanceira.objects.select_related("categoria_pai"), request.user), pk=pk)
    form = CategoriaFinanceiraForm(instance=categoria, user=request.user)
    return render(request, "financeiro/categoria_form.html", {"form": form, "titulo": "Categoria", "categoria": categoria, "somente_leitura": True})


@require_capability("pode_gerenciar_financeiro")
def categoria_editar(request, pk):
    categoria = get_object_or_404(queryset_da_empresa(CategoriaFinanceira.objects.select_related("categoria_pai"), request.user), pk=pk)
    if request.method == "POST":
        form = CategoriaFinanceiraForm(request.POST, instance=categoria, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoria atualizada com sucesso.")
            return redirect("financeiro:categoria_lista")
    else:
        form = CategoriaFinanceiraForm(instance=categoria, user=request.user)
    return render(request, "financeiro/categoria_form.html", {"form": form, "titulo": "Editar categoria", "categoria": categoria})


@require_capability("pode_gerenciar_financeiro")
def categoria_excluir(request, pk):
    categoria = get_object_or_404(queryset_da_empresa(CategoriaFinanceira.objects.all(), request.user), pk=pk)
    acao = "reativar" if not categoria.ativa else "inativar"
    if request.method == "POST":
        categoria.ativa = not categoria.ativa
        categoria.save(update_fields=["ativa", "atualizado_em"])
        messages.success(request, "Categoria reativada com sucesso." if categoria.ativa else "Categoria inativada com sucesso.")
        return redirect("financeiro:categoria_lista")
    return render(request, "financeiro/confirmar_status.html", {"objeto": categoria, "tipo": "categoria", "acao": acao, "voltar_url": "financeiro:categoria_lista"})


@require_capability("pode_visualizar_financeiro")
def transacao_lista(request):
    busca = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    status = request.GET.get("status", "").strip()
    conta_id = request.GET.get("conta", "").strip()
    transacoes = queryset_da_empresa(Transacao.objects.select_related("conta", "conta_destino", "categoria"), request.user)
    if tipo in {"receita", "despesa", "transferencia"}:
        transacoes = transacoes.filter(tipo=tipo)
    if status in {"pendente", "pago", "cancelado"}:
        transacoes = transacoes.filter(status=status)
    if conta_id:
        transacoes = transacoes.filter(Q(conta_id=conta_id) | Q(conta_destino_id=conta_id))
    if busca:
        transacoes = filter_ranked_search(transacoes, busca, ("descricao", "observacoes", "categoria__nome", "conta__nome"))
    page_obj = paginate_queryset(request, transacoes, per_page=25)
    contas = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), request.user)
    return render(request, "financeiro/transacao_lista.html", {"transacoes": page_obj, "page_obj": page_obj, "busca": busca, "tipo": tipo, "status": status, "conta": conta_id, "contas": contas})


@require_capability("pode_gerenciar_financeiro")
def transacao_criar(request):
    if request.method == "POST":
        form = TransacaoForm(request.POST, user=request.user)
        if form.is_valid():
            transacao = form.save(commit=False)
            transacao.empresa = obter_grupo_empresa_ou_erro(request.user)
            transacao.criado_por = request.user
            transacao.save()
            messages.success(request, "Transação criada com sucesso.")
            return redirect("financeiro:transacao_lista")
    else:
        form = TransacaoForm(user=request.user, initial={"data_competencia": timezone.localdate()})
    return render(request, "financeiro/transacao_form.html", {"form": form, "titulo": "Nova transação"})


@require_capability("pode_visualizar_financeiro")
def transacao_visualizar(request, pk):
    transacao = get_object_or_404(queryset_da_empresa(Transacao.objects.select_related("conta", "conta_destino", "categoria"), request.user), pk=pk)
    form = TransacaoForm(instance=transacao, user=request.user)
    return render(request, "financeiro/transacao_form.html", {"form": form, "titulo": "Transação", "transacao": transacao, "somente_leitura": True})


@require_capability("pode_gerenciar_financeiro")
def transacao_editar(request, pk):
    transacao = get_object_or_404(queryset_da_empresa(Transacao.objects.select_related("conta", "conta_destino", "categoria"), request.user), pk=pk)
    if request.method == "POST":
        form = TransacaoForm(request.POST, instance=transacao, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Transação atualizada com sucesso.")
            return redirect("financeiro:transacao_lista")
    else:
        form = TransacaoForm(instance=transacao, user=request.user)
    return render(request, "financeiro/transacao_form.html", {"form": form, "titulo": "Editar transação", "transacao": transacao})


@require_capability("pode_gerenciar_financeiro")
def transacao_excluir(request, pk):
    transacao = get_object_or_404(queryset_da_empresa(Transacao.objects.all(), request.user), pk=pk)
    if request.method == "POST":
        transacao.status = "cancelado"
        transacao.save(update_fields=["status", "atualizado_em"])
        messages.success(request, "Transação cancelada com sucesso.")
        return redirect("financeiro:transacao_lista")
    return render(request, "financeiro/confirmar_status.html", {"objeto": transacao, "tipo": "transação", "acao": "cancelar", "voltar_url": "financeiro:transacao_lista"})


@require_capability("pode_gerenciar_financeiro")
@require_POST
def transacao_marcar_pago(request, pk):
    transacao = get_object_or_404(queryset_da_empresa(Transacao.objects.all(), request.user), pk=pk)
    transacao.status = "pago"
    if not transacao.data_pagamento:
        transacao.data_pagamento = timezone.localdate()
    transacao.save(update_fields=["status", "data_pagamento", "atualizado_em"])
    messages.success(request, "Transação marcada como paga.")
    return redirect("financeiro:transacao_lista")
