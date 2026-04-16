from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import require_capability
from core.query import paginate_queryset
from core.search import filter_ranked_search
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from .forms import CategoriaItemForm, ImportarCatalogoExcelForm, ItemCatalogoForm
from .models import CategoriaItem, ItemCatalogo


def obter_queryset_itens_catalogo(request):
    busca = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    ativo = request.GET.get("ativo", "ativos").strip()
    ordenar = request.GET.get("sort", "nome")

    itens = queryset_da_empresa(ItemCatalogo.objects.select_related("categoria").all(), request.user)

    if categoria_id:
        itens = itens.filter(categoria_id=categoria_id)

    if ativo != "inativos":
        itens = itens.filter(ativo=True)
    else:
        itens = itens.filter(ativo=False)

    ordenacoes = {
        "nome": "nome",
        "codigo": "codigo",
        "categoria": "categoria__nome",
        "preco_maior": "-valor_unitario_padrao",
        "preco_menor": "valor_unitario_padrao",
        "recentes": "-atualizado_em",
    }
    itens = itens.order_by(ordenacoes.get(ordenar, "nome"))
    if busca:
        itens = filter_ranked_search(
            itens,
            busca,
            ("codigo", "nome", "descricao_padrao", "categoria__nome"),
        )
    return itens, busca, categoria_id, ativo, ordenar


@require_capability("pode_visualizar_catalogo")
def categoria_lista(request):
    busca = request.GET.get("q", "").strip()
    ativo = request.GET.get("ativo", "ativas").strip()
    ordenar = request.GET.get("sort", "nome")

    categorias = queryset_da_empresa(CategoriaItem.objects.all(), request.user)

    if ativo != "inativas":
        categorias = categorias.filter(ativo=True)
    else:
        categorias = categorias.filter(ativo=False)

    ordenacoes = {
        "nome": "nome",
        "recentes": "-atualizado_em",
    }
    categorias = categorias.order_by(ordenacoes.get(ordenar, "nome"))
    if busca:
        categorias = filter_ranked_search(categorias, busca, ("nome",))
    page_obj = paginate_queryset(request, categorias, per_page=12)

    context = {
        "categorias": page_obj,
        "page_obj": page_obj,
        "busca": busca,
        "ativo": ativo,
        "sort": ordenar,
    }
    return render(request, "catalogo/categoria_lista.html", context)


@require_capability("pode_gerenciar_catalogo")
def categoria_criar(request):
    if request.method == "POST":
        form = CategoriaItemForm(request.POST, user=request.user)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.empresa = obter_grupo_empresa_ou_erro(request.user)
            categoria.save()
            return redirect("catalogo:categoria_lista")
    else:
        form = CategoriaItemForm(user=request.user)

    return render(
        request,
        "catalogo/categoria_form.html",
        {"form": form, "titulo": "Nova categoria"},
    )


@require_capability("pode_visualizar_catalogo")
def categoria_visualizar(request, pk):
    categoria = get_object_or_404(queryset_da_empresa(CategoriaItem.objects.all(), request.user), pk=pk)
    form = CategoriaItemForm(instance=categoria, user=request.user)
    return render(
        request,
        "catalogo/categoria_form.html",
        {"form": form, "titulo": "Categoria", "categoria": categoria, "somente_leitura": True},
    )


@require_capability("pode_gerenciar_catalogo")
def categoria_editar(request, pk):
    categoria = get_object_or_404(queryset_da_empresa(CategoriaItem.objects.all(), request.user), pk=pk)
    cor_anterior = categoria.cor

    if request.method == "POST":
        form = CategoriaItemForm(request.POST, instance=categoria, user=request.user)
        if form.is_valid():
            categoria = form.save()
            if categoria.cor != cor_anterior:
                messages.success(
                    request,
                    "Cor da categoria atualizada. Os itens do catálogo e os orçamentos ainda não enviados passam a usar a nova cor.",
                )
            else:
                messages.success(
                    request,
                    "Categoria atualizada. Os itens do catálogo e os orçamentos ainda não enviados passam a usar os dados mais recentes desta categoria.",
                )
            return redirect("catalogo:categoria_lista")
    else:
        form = CategoriaItemForm(instance=categoria, user=request.user)

    return render(
        request,
        "catalogo/categoria_form.html",
        {"form": form, "titulo": "Editar categoria", "categoria": categoria},
    )


@require_capability("pode_gerenciar_catalogo")
def categoria_excluir(request, pk):
    categoria = get_object_or_404(queryset_da_empresa(CategoriaItem.objects.all(), request.user), pk=pk)
    acao = "reativar" if not categoria.ativo else "inativar"

    if request.method == "POST":
        categoria.ativo = not categoria.ativo
        categoria.save(update_fields=["ativo", "atualizado_em"])
        if categoria.ativo:
            messages.success(request, "Categoria reativada com sucesso.")
        else:
            messages.success(request, "Categoria inativada com sucesso.")
        return redirect("catalogo:categoria_lista")

    return render(
        request,
        "catalogo/categoria_excluir.html",
        {"categoria": categoria, "acao": acao},
    )


@require_capability("pode_visualizar_catalogo")
def item_lista(request):
    itens, busca, categoria_id, ativo, ordenar = obter_queryset_itens_catalogo(request)
    page_obj = paginate_queryset(request, itens, per_page=25)

    context = {
        "itens": page_obj,
        "page_obj": page_obj,
        "busca": busca,
        "categoria": categoria_id,
        "ativo": ativo,
        "sort": ordenar,
        "categorias": queryset_da_empresa(CategoriaItem.objects.filter(ativo=True).order_by("nome"), request.user),
    }
    return render(request, "catalogo/item_lista.html", context)


@require_capability("pode_visualizar_catalogo")
def item_exportar_excel(request):
    from .services import exportar_catalogo_excel

    itens, *_ = obter_queryset_itens_catalogo(request)
    conteudo = exportar_catalogo_excel(itens)

    response = HttpResponse(conteudo, content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="catalogo-itens.xls"'
    return response


@require_capability("pode_gerenciar_catalogo")
def item_criar(request):
    if request.method == "POST":
        form = ItemCatalogoForm(request.POST, user=request.user)
        if form.is_valid():
            item = form.save(commit=False)
            item.empresa = obter_grupo_empresa_ou_erro(request.user)
            if item.categoria and item.categoria.empresa_id != item.empresa_id:
                form.add_error("categoria", "Selecione uma categoria da sua empresa.")
            else:
                item.save()
                return redirect("catalogo:item_lista")
    else:
        form = ItemCatalogoForm(user=request.user)

    return render(
        request,
        "catalogo/item_form.html",
        {"form": form, "titulo": "Novo item"},
    )


@require_capability("pode_visualizar_catalogo")
def item_visualizar(request, pk):
    item = get_object_or_404(queryset_da_empresa(ItemCatalogo.objects.select_related("categoria"), request.user), pk=pk)
    form = ItemCatalogoForm(instance=item, user=request.user)
    return render(
        request,
        "catalogo/item_form.html",
        {"form": form, "titulo": "Item do catálogo", "item": item, "somente_leitura": True},
    )


@require_capability("pode_gerenciar_catalogo")
def item_editar(request, pk):
    item = get_object_or_404(queryset_da_empresa(ItemCatalogo.objects.select_related("categoria"), request.user), pk=pk)

    if request.method == "POST":
        form = ItemCatalogoForm(request.POST, instance=item, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("catalogo:item_lista")
    else:
        form = ItemCatalogoForm(instance=item, user=request.user)

    return render(
        request,
        "catalogo/item_form.html",
        {"form": form, "titulo": "Editar item", "item": item},
    )


@require_capability("pode_gerenciar_catalogo")
def item_excluir(request, pk):
    item = get_object_or_404(queryset_da_empresa(ItemCatalogo.objects.select_related("categoria"), request.user), pk=pk)
    acao = "reativar" if not item.ativo else "inativar"

    if request.method == "POST":
        item.ativo = not item.ativo
        item.save(update_fields=["ativo", "atualizado_em"])
        if item.ativo:
            messages.success(request, "Item reativado com sucesso.")
        else:
            messages.success(request, "Item inativado com sucesso.")
        return redirect("catalogo:item_lista")

    return render(
        request,
        "catalogo/item_excluir.html",
        {"item": item, "acao": acao},
    )


@require_capability("pode_gerenciar_catalogo")
def catalogo_importar_excel(request):
    if request.method == "POST":
        form = ImportarCatalogoExcelForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                from .services import importar_catalogo_excel

                categorias_criadas, itens_criados = importar_catalogo_excel(
                    form.cleaned_data["arquivo"],
                    obter_grupo_empresa_ou_erro(request.user),
                )
            except ValueError as exc:
                form.add_error("arquivo", str(exc))
            except Exception:
                form.add_error(
                    "arquivo",
                    "Não foi possível importar o arquivo. Revise as colunas, valores e unidades antes de tentar novamente.",
                )
            else:
                messages.success(
                    request,
                    f"Importação concluída: {categorias_criadas} categorias e {itens_criados} itens processados.",
                )
                return redirect("catalogo:item_lista")
    else:
        form = ImportarCatalogoExcelForm()

    return render(
        request,
        "catalogo/importar_excel.html",
        {"form": form, "titulo": "Importar categorias e itens"},
    )
