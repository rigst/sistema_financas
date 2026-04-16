import uuid

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import require_capability
from core.query import paginate_queryset
from core.search import filter_ranked_search
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from .forms import (
    CategoriaFinanceiraForm,
    CartaoCreditoForm,
    CompraCartaoForm,
    ContaForm,
    FaturaCartaoForm,
    FaturaPagamentoForm,
    TransacaoForm,
)
from .models import CategoriaFinanceira, CartaoCredito, Conta, FaturaCartao, LancamentoCartao, Transacao


def adicionar_meses(mes, ano, incremento):
    total = (ano * 12) + (mes - 1) + incremento
    return (total % 12) + 1, total // 12


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



@require_capability("pode_visualizar_financeiro")
def cartao_lista(request):
    busca = request.GET.get("q", "").strip()
    ativo = request.GET.get("ativo", "ativos").strip()
    cartoes = queryset_da_empresa(CartaoCredito.objects.select_related("conta_pagamento"), request.user)
    cartoes = cartoes.filter(ativo=(ativo != "inativos")).order_by("nome")
    if busca:
        cartoes = filter_ranked_search(cartoes, busca, ("nome", "bandeira", "conta_pagamento__nome"))
    page_obj = paginate_queryset(request, cartoes, per_page=20)
    return render(request, "financeiro/cartao_lista.html", {"cartoes": page_obj, "page_obj": page_obj, "busca": busca, "ativo": ativo})


@require_capability("pode_gerenciar_financeiro")
def cartao_criar(request):
    if request.method == "POST":
        form = CartaoCreditoForm(request.POST, user=request.user)
        if form.is_valid():
            cartao = form.save(commit=False)
            cartao.empresa = obter_grupo_empresa_ou_erro(request.user)
            cartao.save()
            messages.success(request, "Cartão criado com sucesso.")
            return redirect("financeiro:cartao_lista")
    else:
        form = CartaoCreditoForm(user=request.user)
    return render(request, "financeiro/cartao_form.html", {"form": form, "titulo": "Novo cartão"})


@require_capability("pode_visualizar_financeiro")
def cartao_visualizar(request, pk):
    cartao = get_object_or_404(queryset_da_empresa(CartaoCredito.objects.select_related("conta_pagamento"), request.user), pk=pk)
    form = CartaoCreditoForm(instance=cartao, user=request.user)
    return render(request, "financeiro/cartao_form.html", {"form": form, "titulo": "Cartão", "cartao": cartao, "somente_leitura": True})


@require_capability("pode_gerenciar_financeiro")
def cartao_editar(request, pk):
    cartao = get_object_or_404(queryset_da_empresa(CartaoCredito.objects.select_related("conta_pagamento"), request.user), pk=pk)
    if request.method == "POST":
        form = CartaoCreditoForm(request.POST, instance=cartao, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Cartão atualizado com sucesso.")
            return redirect("financeiro:cartao_lista")
    else:
        form = CartaoCreditoForm(instance=cartao, user=request.user)
    return render(request, "financeiro/cartao_form.html", {"form": form, "titulo": "Editar cartão", "cartao": cartao})


@require_capability("pode_gerenciar_financeiro")
def cartao_excluir(request, pk):
    cartao = get_object_or_404(queryset_da_empresa(CartaoCredito.objects.all(), request.user), pk=pk)
    acao = "reativar" if not cartao.ativo else "inativar"
    if request.method == "POST":
        cartao.ativo = not cartao.ativo
        cartao.save(update_fields=["ativo", "atualizado_em"])
        messages.success(request, "Cartão reativado com sucesso." if cartao.ativo else "Cartão inativado com sucesso.")
        return redirect("financeiro:cartao_lista")
    return render(request, "financeiro/confirmar_status.html", {"objeto": cartao, "tipo": "cartão", "acao": acao, "voltar_url": "financeiro:cartao_lista"})


@require_capability("pode_visualizar_financeiro")
def fatura_lista(request):
    status = request.GET.get("status", "").strip()
    cartao_id = request.GET.get("cartao", "").strip()
    faturas = queryset_da_empresa(FaturaCartao.objects.select_related("cartao", "conta_pagamento"), request.user)
    if status in {"aberta", "fechada", "paga", "cancelada"}:
        faturas = faturas.filter(status=status)
    if cartao_id:
        faturas = faturas.filter(cartao_id=cartao_id)
    page_obj = paginate_queryset(request, faturas, per_page=20)
    cartoes = queryset_da_empresa(CartaoCredito.objects.filter(ativo=True).order_by("nome"), request.user)
    return render(request, "financeiro/fatura_lista.html", {"faturas": page_obj, "page_obj": page_obj, "status": status, "cartao": cartao_id, "cartoes": cartoes})


@require_capability("pode_gerenciar_financeiro")
def fatura_criar(request):
    if request.method == "POST":
        form = FaturaCartaoForm(request.POST, user=request.user)
        if form.is_valid():
            fatura = form.save(commit=False)
            fatura.empresa = obter_grupo_empresa_ou_erro(request.user)
            fatura.save()
            messages.success(request, "Fatura criada com sucesso.")
            return redirect("financeiro:fatura_visualizar", pk=fatura.pk)
    else:
        form = FaturaCartaoForm(user=request.user)
    return render(request, "financeiro/fatura_form.html", {"form": form, "titulo": "Nova fatura"})


@require_capability("pode_visualizar_financeiro")
def fatura_visualizar(request, pk):
    fatura = get_object_or_404(queryset_da_empresa(FaturaCartao.objects.select_related("cartao", "conta_pagamento", "categoria_pagamento"), request.user), pk=pk)
    lancamentos = fatura.lancamentos.select_related("categoria").all()
    pagamento_form = FaturaPagamentoForm(user=request.user, fatura=fatura, initial={"data_pagamento": timezone.localdate()})
    return render(request, "financeiro/fatura_detalhe.html", {"fatura": fatura, "lancamentos": lancamentos, "pagamento_form": pagamento_form})


@require_capability("pode_gerenciar_financeiro")
def fatura_editar(request, pk):
    fatura = get_object_or_404(queryset_da_empresa(FaturaCartao.objects.select_related("cartao"), request.user), pk=pk)
    if request.method == "POST":
        form = FaturaCartaoForm(request.POST, instance=fatura, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Fatura atualizada com sucesso.")
            return redirect("financeiro:fatura_visualizar", pk=fatura.pk)
    else:
        form = FaturaCartaoForm(instance=fatura, user=request.user)
    return render(request, "financeiro/fatura_form.html", {"form": form, "titulo": "Editar fatura", "fatura": fatura})


@require_capability("pode_gerenciar_financeiro")
@require_POST
def fatura_pagar(request, pk):
    fatura = get_object_or_404(queryset_da_empresa(FaturaCartao.objects.select_related("cartao"), request.user), pk=pk)
    form = FaturaPagamentoForm(request.POST, user=request.user, fatura=fatura)
    if form.is_valid():
        fatura.pagar(
            conta=form.cleaned_data["conta_pagamento"],
            categoria=form.cleaned_data["categoria_pagamento"],
            data_pagamento=form.cleaned_data["data_pagamento"],
            usuario=request.user,
        )
        messages.success(request, "Fatura paga e transação bancária criada.")
    else:
        messages.error(request, "Não foi possível pagar a fatura. Revise conta, categoria e data.")
    return redirect("financeiro:fatura_visualizar", pk=fatura.pk)


@require_capability("pode_gerenciar_financeiro")
def compra_cartao_criar(request):
    if request.method == "POST":
        form = CompraCartaoForm(request.POST, user=request.user)
        if form.is_valid():
            empresa = obter_grupo_empresa_ou_erro(request.user)
            cartao = form.cleaned_data["cartao"]
            categoria = form.cleaned_data["categoria"]
            descricao = form.cleaned_data["descricao"].strip()
            data_compra = form.cleaned_data["data_compra"]
            observacoes = form.cleaned_data["observacoes"].strip()
            mes_inicial = form.cleaned_data["mes_primeira_fatura"]
            ano_inicial = form.cleaned_data["ano_primeira_fatura"]
            parcelas = form.cleaned_data["parcelas"]
            grupo = uuid.uuid4().hex
            primeira_fatura = None
            for idx, valor in enumerate(form.valores_parcelas(), start=1):
                mes, ano = adicionar_meses(mes_inicial, ano_inicial, idx - 1)
                fatura, _ = FaturaCartao.objects.get_or_create(
                    empresa=empresa,
                    cartao=cartao,
                    mes=mes,
                    ano=ano,
                    defaults={"conta_pagamento": cartao.conta_pagamento, "status": "aberta"},
                )
                if primeira_fatura is None:
                    primeira_fatura = fatura
                LancamentoCartao.objects.create(
                    fatura=fatura,
                    cartao=cartao,
                    categoria=categoria,
                    descricao=descricao,
                    valor=valor,
                    data_compra=data_compra,
                    parcela_numero=idx,
                    parcela_total=parcelas,
                    grupo_parcelamento=grupo if parcelas > 1 else "",
                    observacoes=observacoes,
                    empresa=empresa,
                    criado_por=request.user,
                )
            messages.success(request, "Compra lançada no cartão com sucesso.")
            if primeira_fatura is not None:
                return redirect("financeiro:fatura_visualizar", pk=primeira_fatura.pk)
            return redirect("financeiro:fatura_lista")
    else:
        hoje = timezone.localdate()
        form = CompraCartaoForm(user=request.user, initial={"data_compra": hoje, "mes_primeira_fatura": hoje.month, "ano_primeira_fatura": hoje.year, "parcelas": 1})
    return render(request, "financeiro/compra_cartao_form.html", {"form": form, "titulo": "Nova compra no cartão"})


@require_capability("pode_gerenciar_financeiro")
def lancamento_cartao_cancelar(request, pk):
    lancamento = get_object_or_404(queryset_da_empresa(LancamentoCartao.objects.select_related("fatura"), request.user), pk=pk)
    if request.method == "POST":
        lancamento.status = "cancelado"
        lancamento.save(update_fields=["status", "atualizado_em"])
        messages.success(request, "Lançamento cancelado com sucesso.")
        return redirect("financeiro:fatura_visualizar", pk=lancamento.fatura_id)
    return render(request, "financeiro/confirmar_status.html", {"objeto": lancamento, "tipo": "lançamento", "acao": "cancelar", "voltar_url": "financeiro:fatura_lista"})
