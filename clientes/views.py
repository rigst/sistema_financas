from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import require_capability
from core.query import paginate_queryset
from core.search import filter_ranked_search
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from .forms import ClienteForm
from .models import Cliente


@require_capability("pode_visualizar_clientes")
def cliente_lista(request):
    busca = request.GET.get("q", "").strip()
    ativo = request.GET.get("ativo", "ativos").strip()
    ordenar = request.GET.get("sort", "nome")

    clientes = queryset_da_empresa(Cliente.objects.all(), request.user)

    if ativo != "inativos":
        clientes = clientes.filter(ativo=True)
    else:
        clientes = clientes.filter(ativo=False)

    ordenacoes = {
        "nome": "nome_razao_social",
        "tipo": "tipo_pessoa",
        "cidade": "cidade",
        "recentes": "-atualizado_em",
    }
    clientes = clientes.order_by(ordenacoes.get(ordenar, "nome_razao_social"))
    if busca:
        clientes = filter_ranked_search(
            clientes,
            busca,
            ("nome_razao_social", "nome_fantasia", "cpf_cnpj", "email"),
        )
    page_obj = paginate_queryset(request, clientes, per_page=12)

    context = {
        "clientes": page_obj,
        "page_obj": page_obj,
        "busca": busca,
        "ativo": ativo,
        "sort": ordenar,
    }
    return render(request, "clientes/lista.html", context)


@require_capability("pode_gerenciar_clientes")
def cliente_criar(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.empresa = obter_grupo_empresa_ou_erro(request.user)
            cliente.save()
            return redirect("clientes:lista")
    else:
        form = ClienteForm()

    return render(request, "clientes/form.html", {"form": form, "titulo": "Novo cliente"})


@require_capability("pode_visualizar_clientes")
def cliente_visualizar(request, pk):
    cliente = get_object_or_404(queryset_da_empresa(Cliente.objects.all(), request.user), pk=pk)
    form = ClienteForm(instance=cliente)

    return render(
        request,
        "clientes/form.html",
        {"form": form, "titulo": "Cliente", "cliente": cliente, "somente_leitura": True},
    )


@require_capability("pode_gerenciar_clientes")
def cliente_editar(request, pk):
    cliente = get_object_or_404(queryset_da_empresa(Cliente.objects.all(), request.user), pk=pk)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Cliente atualizado. Os orçamentos ainda não enviados passam a usar os dados mais recentes deste cliente.",
            )
            return redirect("clientes:lista")
    else:
        form = ClienteForm(instance=cliente)

    return render(
        request,
        "clientes/form.html",
        {"form": form, "titulo": "Editar cliente", "cliente": cliente},
    )


@require_capability("pode_gerenciar_clientes")
def cliente_excluir(request, pk):
    cliente = get_object_or_404(queryset_da_empresa(Cliente.objects.all(), request.user), pk=pk)
    acao = "reativar" if not cliente.ativo else "inativar"

    if request.method == "POST":
        cliente.ativo = not cliente.ativo
        cliente.save(update_fields=["ativo", "atualizado_em"])
        if cliente.ativo:
            messages.success(request, "Cliente reativado com sucesso.")
        else:
            messages.success(request, "Cliente inativado com sucesso.")
        return redirect("clientes:lista")

    return render(
        request,
        "clientes/excluir.html",
        {"cliente": cliente, "acao": acao},
    )
