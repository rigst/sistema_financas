import calendar
import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from core.permissions import require_capability
from core.formatting import parse_decimal_br
from core.query import get_bounded_int_param, paginate_queryset
from core.search import filter_ranked_search
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from .forms import (
    CategoriaFinanceiraForm,
    CartaoCreditoForm,
    CompraCartaoForm,
    ContaForm,
    FaturaCartaoForm,
    FaturaPagamentoForm,
    MetaFinanceiraForm,
    PlanejamentoMensalForm,
    RecorrenciaFinanceiraForm,
    TransacaoImportCSVForm,
    TransacaoForm,
)
from .models import (
    CategoriaFinanceira,
    CartaoCredito,
    Conta,
    FaturaCartao,
    LancamentoCartao,
    MetaFinanceira,
    PlanejamentoMensal,
    RecorrenciaFinanceira,
    Transacao,
    arredondar,
)


def adicionar_meses(mes, ano, incremento):
    total = (ano * 12) + (mes - 1) + incremento
    return (total % 12) + 1, total // 12


def data_recorrencia(base, frequencia, indice, dia_vencimento):
    if frequencia == "semanal":
        return base + timedelta(days=7 * indice)
    if frequencia == "quinzenal":
        return base + timedelta(days=14 * indice)
    if frequencia == "anual":
        mes, ano = base.month, base.year + indice
    else:
        mes, ano = adicionar_meses(base.month, base.year, indice)
    dia = min(dia_vencimento, calendar.monthrange(ano, mes)[1])
    return base.replace(year=ano, month=mes, day=dia)


def _normalizar_lookup(valor):
    return (valor or "").strip().casefold()


def _transacoes_filtradas(request):
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
    return transacoes, busca, tipo, status, conta_id


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
    transacoes, busca, tipo, status, conta_id = _transacoes_filtradas(request)
    page_obj = paginate_queryset(request, transacoes, per_page=25)
    contas = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), request.user)
    return render(request, "financeiro/transacao_lista.html", {"transacoes": page_obj, "page_obj": page_obj, "busca": busca, "tipo": tipo, "status": status, "conta": conta_id, "contas": contas})


@require_capability("pode_visualizar_financeiro")
def transacao_exportar_csv(request):
    transacoes, *_ = _transacoes_filtradas(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="transacoes.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow([
        "tipo",
        "descricao",
        "valor",
        "data_competencia",
        "status",
        "conta",
        "categoria",
        "conta_destino",
        "data_pagamento",
        "observacoes",
    ])
    for item in transacoes.order_by("data_competencia", "id"):
        writer.writerow([
            item.tipo,
            item.descricao,
            item.valor,
            item.data_competencia.isoformat(),
            item.status,
            item.conta.nome,
            item.categoria.nome if item.categoria_id else "",
            item.conta_destino.nome if item.conta_destino_id else "",
            item.data_pagamento.isoformat() if item.data_pagamento else "",
            item.observacoes,
        ])
    return response


@require_capability("pode_gerenciar_financeiro")
def transacao_importar_csv(request):
    empresa = obter_grupo_empresa_ou_erro(request.user)
    if request.method == "POST":
        form = TransacaoImportCSVForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = form.cleaned_data["arquivo"]
            try:
                texto = arquivo.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                form.add_error("arquivo", "O CSV deve estar em UTF-8.")
            else:
                reader = csv.DictReader(io.StringIO(texto))
                obrigatorias = {"tipo", "descricao", "valor", "data_competencia", "conta"}
                headers = set(reader.fieldnames or [])
                if not obrigatorias.issubset(headers):
                    form.add_error("arquivo", "CSV sem colunas obrigatórias: tipo, descricao, valor, data_competencia e conta.")
                else:
                    contas = {
                        _normalizar_lookup(conta.nome): conta
                        for conta in queryset_da_empresa(Conta.objects.filter(ativa=True), request.user)
                    }
                    categorias = {
                        (categoria.tipo, _normalizar_lookup(categoria.nome)): categoria
                        for categoria in queryset_da_empresa(CategoriaFinanceira.objects.filter(ativa=True), request.user)
                    }
                    criadas = 0
                    erros = []
                    linhas = list(reader)
                    if len(linhas) > 1000:
                        form.add_error("arquivo", "Importe no máximo 1000 transações por arquivo.")
                    else:
                        with transaction.atomic():
                            for numero, linha in enumerate(linhas, start=2):
                                erros_linha = []
                                tipo = (linha.get("tipo") or "").strip()
                                status = (linha.get("status") or "pendente").strip() or "pendente"
                                conta = contas.get(_normalizar_lookup(linha.get("conta")))
                                conta_destino = contas.get(_normalizar_lookup(linha.get("conta_destino")))
                                categoria = categorias.get((tipo, _normalizar_lookup(linha.get("categoria"))))
                                data_competencia = parse_date((linha.get("data_competencia") or "").strip())
                                data_pagamento_raw = (linha.get("data_pagamento") or "").strip()
                                data_pagamento = parse_date(data_pagamento_raw) if data_pagamento_raw else None
                                descricao = (linha.get("descricao") or "").strip()
                                try:
                                    valor = parse_decimal_br(linha.get("valor"))
                                except ValueError:
                                    valor = None

                                if not descricao:
                                    erros_linha.append(f"Linha {numero}: descrição obrigatória.")
                                if tipo not in {"receita", "despesa", "transferencia"}:
                                    erros_linha.append(f"Linha {numero}: tipo inválido.")
                                if status not in {"pendente", "pago", "cancelado"}:
                                    erros_linha.append(f"Linha {numero}: status inválido.")
                                if not conta:
                                    erros_linha.append(f"Linha {numero}: conta não encontrada.")
                                if tipo == "transferencia" and not conta_destino:
                                    erros_linha.append(f"Linha {numero}: transferência exige conta_destino.")
                                if tipo in {"receita", "despesa"} and not categoria:
                                    erros_linha.append(f"Linha {numero}: categoria não encontrada para o tipo informado.")
                                if not data_competencia:
                                    erros_linha.append(f"Linha {numero}: data_competencia inválida.")
                                if data_pagamento_raw and not data_pagamento:
                                    erros_linha.append(f"Linha {numero}: data_pagamento inválida.")
                                if not valor or valor <= 0:
                                    erros_linha.append(f"Linha {numero}: valor inválido.")
                                if erros_linha:
                                    erros.extend(erros_linha)
                                    continue

                                try:
                                    Transacao.objects.create(
                                        tipo=tipo,
                                        descricao=descricao,
                                        valor=valor,
                                        data_competencia=data_competencia,
                                        data_pagamento=data_pagamento,
                                        status=status,
                                        conta=conta,
                                        conta_destino=conta_destino if tipo == "transferencia" else None,
                                        categoria=categoria if tipo != "transferencia" else None,
                                        observacoes=(linha.get("observacoes") or "").strip(),
                                        empresa=empresa,
                                        criado_por=request.user,
                                    )
                                except ValidationError as exc:
                                    erros.append(f"Linha {numero}: {'; '.join(exc.messages)}")
                                    continue
                                criadas += 1
                            if erros:
                                transaction.set_rollback(True)
                                form.add_error(None, "Corrija o CSV antes de importar: " + " ".join(erros[:10]))
                            else:
                                messages.success(request, f"{criadas} transação(ões) importada(s) com sucesso.")
                                return redirect("financeiro:transacao_lista")
    else:
        form = TransacaoImportCSVForm()
    return render(request, "financeiro/transacao_importar.html", {"form": form})


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
    fatura_base = get_object_or_404(queryset_da_empresa(FaturaCartao.objects.select_related("cartao"), request.user), pk=pk)
    form = FaturaPagamentoForm(request.POST, user=request.user, fatura=fatura_base)
    if form.is_valid():
        try:
            with transaction.atomic():
                fatura = queryset_da_empresa(
                    FaturaCartao.objects.select_for_update().select_related("cartao"),
                    request.user,
                ).get(pk=pk)
                fatura.pagar(
                    conta=form.cleaned_data["conta_pagamento"],
                    categoria=form.cleaned_data["categoria_pagamento"],
                    data_pagamento=form.cleaned_data["data_pagamento"],
                    usuario=request.user,
                )
            messages.success(request, "Fatura paga e transação bancária criada.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
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
            periodos = [adicionar_meses(mes_inicial, ano_inicial, idx) for idx in range(parcelas)]
            filtro_periodos = Q()
            for mes, ano in periodos:
                filtro_periodos |= Q(mes=mes, ano=ano)
            bloqueada = FaturaCartao.objects.filter(
                filtro_periodos,
                empresa=empresa,
                cartao=cartao,
                status__in=["paga", "cancelada"],
            ).first()
            if bloqueada:
                form.add_error(None, f"A fatura {bloqueada} está {bloqueada.get_status_display().lower()} e não aceita novos lançamentos.")
                return render(request, "financeiro/compra_cartao_form.html", {"form": form, "titulo": "Nova compra no cartão"})

            grupo = uuid.uuid4().hex
            primeira_fatura = None
            with transaction.atomic():
                for idx, valor in enumerate(form.valores_parcelas(), start=1):
                    mes, ano = adicionar_meses(mes_inicial, ano_inicial, idx - 1)
                    fatura, _ = FaturaCartao.objects.get_or_create(
                        empresa=empresa,
                        cartao=cartao,
                        mes=mes,
                        ano=ano,
                        defaults={"conta_pagamento": cartao.conta_pagamento, "status": "aberta"},
                    )
                    if fatura.status in {"paga", "cancelada"}:
                        raise ValidationError(f"A fatura {fatura} não aceita novos lançamentos.")
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
        if lancamento.fatura.status in {"paga", "cancelada"}:
            messages.error(request, "Não é possível cancelar lançamentos de fatura paga ou cancelada.")
            return redirect("financeiro:fatura_visualizar", pk=lancamento.fatura_id)
        lancamento.status = "cancelado"
        lancamento.save(update_fields=["status", "atualizado_em"])
        messages.success(request, "Lançamento cancelado com sucesso.")
        return redirect("financeiro:fatura_visualizar", pk=lancamento.fatura_id)
    return render(request, "financeiro/confirmar_status.html", {"objeto": lancamento, "tipo": "lançamento", "acao": "cancelar", "voltar_url": "financeiro:fatura_lista"})


@require_capability("pode_visualizar_financeiro")
def relatorio_fluxo_caixa(request):
    hoje = timezone.localdate()
    mes = get_bounded_int_param(request, "mes", hoje.month, minimum=1, maximum=12)
    ano = get_bounded_int_param(request, "ano", hoje.year, minimum=2000, maximum=2100)
    transacoes = queryset_da_empresa(Transacao.objects.select_related("conta", "categoria").exclude(status="cancelado"), request.user).filter(data_competencia__year=ano, data_competencia__month=mes)
    soma_field = DecimalField(max_digits=14, decimal_places=2)
    receitas = transacoes.filter(tipo="receita", status="pago").aggregate(total=Coalesce(Sum("valor"), Value(0), output_field=soma_field))["total"]
    despesas = transacoes.filter(tipo="despesa", status="pago").aggregate(total=Coalesce(Sum("valor"), Value(0), output_field=soma_field))["total"]
    por_categoria = transacoes.filter(status="pago", categoria__isnull=False).values("tipo", "categoria__nome", "categoria__cor").annotate(total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)).order_by("tipo", "-total")
    por_conta = transacoes.filter(status="pago").values("conta__nome").annotate(total=Coalesce(Sum("valor"), Value(0), output_field=soma_field)).order_by("conta__nome")
    return render(request, "financeiro/relatorio_fluxo_caixa.html", {"mes": mes, "ano": ano, "receitas": receitas, "despesas": despesas, "resultado": arredondar(receitas - despesas), "por_categoria": por_categoria, "por_conta": por_conta, "transacoes": transacoes.order_by("-data_competencia")})


@require_capability("pode_visualizar_financeiro")
def planejamento_lista(request):
    hoje = timezone.localdate()
    mes = get_bounded_int_param(request, "mes", hoje.month, minimum=1, maximum=12)
    ano = get_bounded_int_param(request, "ano", hoje.year, minimum=2000, maximum=2100)
    planejamentos = queryset_da_empresa(PlanejamentoMensal.objects.select_related("categoria"), request.user).filter(mes=mes, ano=ano)
    transacoes = queryset_da_empresa(Transacao.objects.filter(tipo="despesa", status="pago", data_competencia__year=ano, data_competencia__month=mes), request.user)
    realizados = {item["categoria_id"]: item["total"] for item in transacoes.values("categoria_id").annotate(total=Coalesce(Sum("valor"), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2)))}
    linhas = []
    for planejamento in planejamentos:
        realizado = arredondar(realizados.get(planejamento.categoria_id, Decimal("0.00")))
        linhas.append({"planejamento": planejamento, "realizado": realizado, "saldo": arredondar(planejamento.valor_planejado - realizado)})
    return render(request, "financeiro/planejamento_lista.html", {"linhas": linhas, "mes": mes, "ano": ano})


@require_capability("pode_gerenciar_financeiro")
def planejamento_criar(request):
    if request.method == "POST":
        form = PlanejamentoMensalForm(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa = obter_grupo_empresa_ou_erro(request.user)
            obj.save()
            messages.success(request, "Planejamento salvo com sucesso.")
            return redirect("financeiro:planejamento_lista")
    else:
        hoje = timezone.localdate()
        form = PlanejamentoMensalForm(user=request.user, initial={"mes": hoje.month, "ano": hoje.year})
    return render(request, "financeiro/planejamento_form.html", {"form": form, "titulo": "Novo planejamento"})


@require_capability("pode_gerenciar_financeiro")
def planejamento_editar(request, pk):
    obj = get_object_or_404(queryset_da_empresa(PlanejamentoMensal.objects.select_related("categoria"), request.user), pk=pk)
    if request.method == "POST":
        form = PlanejamentoMensalForm(request.POST, instance=obj, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Planejamento atualizado com sucesso.")
            return redirect("financeiro:planejamento_lista")
    else:
        form = PlanejamentoMensalForm(instance=obj, user=request.user)
    return render(request, "financeiro/planejamento_form.html", {"form": form, "titulo": "Editar planejamento"})


@require_capability("pode_visualizar_financeiro")
def meta_lista(request):
    metas = queryset_da_empresa(MetaFinanceira.objects.select_related("conta_vinculada"), request.user).order_by("status", "nome")
    return render(request, "financeiro/meta_lista.html", {"metas": metas})


@require_capability("pode_gerenciar_financeiro")
def meta_criar(request):
    if request.method == "POST":
        form = MetaFinanceiraForm(request.POST, user=request.user)
        if form.is_valid():
            meta = form.save(commit=False)
            meta.empresa = obter_grupo_empresa_ou_erro(request.user)
            meta.save()
            messages.success(request, "Meta criada com sucesso.")
            return redirect("financeiro:meta_lista")
    else:
        form = MetaFinanceiraForm(user=request.user)
    return render(request, "financeiro/meta_form.html", {"form": form, "titulo": "Nova meta"})


@require_capability("pode_gerenciar_financeiro")
def meta_editar(request, pk):
    meta = get_object_or_404(queryset_da_empresa(MetaFinanceira.objects.all(), request.user), pk=pk)
    if request.method == "POST":
        form = MetaFinanceiraForm(request.POST, instance=meta, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Meta atualizada com sucesso.")
            return redirect("financeiro:meta_lista")
    else:
        form = MetaFinanceiraForm(instance=meta, user=request.user)
    return render(request, "financeiro/meta_form.html", {"form": form, "titulo": "Editar meta"})


@require_capability("pode_visualizar_financeiro")
def recorrencia_lista(request):
    recorrencias = queryset_da_empresa(RecorrenciaFinanceira.objects.select_related("conta", "categoria"), request.user).order_by("descricao")
    return render(request, "financeiro/recorrencia_lista.html", {"recorrencias": recorrencias})


@require_capability("pode_gerenciar_financeiro")
def recorrencia_criar(request):
    if request.method == "POST":
        form = RecorrenciaFinanceiraForm(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa = obter_grupo_empresa_ou_erro(request.user)
            obj.criado_por = request.user
            obj.save()
            messages.success(request, "Recorrência criada com sucesso.")
            return redirect("financeiro:recorrencia_lista")
    else:
        form = RecorrenciaFinanceiraForm(user=request.user, initial={"data_inicio": timezone.localdate(), "dia_vencimento": timezone.localdate().day})
    return render(request, "financeiro/recorrencia_form.html", {"form": form, "titulo": "Nova recorrência"})


@require_capability("pode_gerenciar_financeiro")
def recorrencia_editar(request, pk):
    obj = get_object_or_404(queryset_da_empresa(RecorrenciaFinanceira.objects.all(), request.user), pk=pk)
    if request.method == "POST":
        form = RecorrenciaFinanceiraForm(request.POST, instance=obj, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Recorrência atualizada com sucesso.")
            return redirect("financeiro:recorrencia_lista")
    else:
        form = RecorrenciaFinanceiraForm(instance=obj, user=request.user)
    return render(request, "financeiro/recorrencia_form.html", {"form": form, "titulo": "Editar recorrência"})


@require_capability("pode_gerenciar_financeiro")
@require_POST
def recorrencia_gerar(request, pk):
    obj = get_object_or_404(queryset_da_empresa(RecorrenciaFinanceira.objects.select_related("conta", "categoria"), request.user), pk=pk)
    if not obj.ativa:
        messages.error(request, "Recorrência inativa não gera lançamentos.")
        return redirect("financeiro:recorrencia_lista")
    quantidade = 12
    criadas = 0
    for idx in range(quantidade):
        data = data_recorrencia(obj.data_inicio, obj.frequencia, idx, obj.dia_vencimento)
        if obj.data_fim and data > obj.data_fim:
            break
        _, created = Transacao.objects.get_or_create(
            empresa=obj.empresa,
            tipo=obj.tipo,
            descricao=obj.descricao,
            valor=obj.valor,
            data_competencia=data,
            conta=obj.conta,
            categoria=obj.categoria,
            defaults={"status": "pendente", "criado_por": request.user, "observacoes": obj.observacoes},
        )
        criadas += 1 if created else 0
    messages.success(request, f"{criadas} lançamento(s) recorrente(s) gerado(s).")
    return redirect("financeiro:recorrencia_lista")
