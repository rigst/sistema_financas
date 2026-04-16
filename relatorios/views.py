from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from mimetypes import guess_type

from core.permissions import require_capability
from core.query import paginate_queryset
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from orcamentos.models import Orcamento
from .forms import ConfiguracaoEmpresaForm
from .exporters import gerar_excel_orcamento, gerar_pdf_orcamento, obter_alerta_status
from .exporters import gerar_pdf_memorial_descritivo, gerar_word_memorial_descritivo
from .models import ConfiguracaoEmpresa


@require_capability("pode_visualizar_relatorios")
def configuracao_lista(request):
    busca = request.GET.get("q", "").strip()
    ativo = request.GET.get("ativo", "ativos").strip()
    ordenar = request.GET.get("sort", "recentes")
    configuracoes = queryset_da_empresa(ConfiguracaoEmpresa.objects.all(), request.user)
    if busca:
        configuracoes = configuracoes.filter(
            Q(nome_empresa__icontains=busca)
            | Q(nome_fantasia__icontains=busca)
            | Q(email__icontains=busca)
            | Q(cidade__icontains=busca)
        )
    if ativo != "inativos":
        configuracoes = configuracoes.filter(ativo=True)
    else:
        configuracoes = configuracoes.filter(ativo=False)
    ordenacoes = {
        "nome": "nome_empresa",
        "cidade": "cidade",
        "recentes": "-atualizado_em",
    }
    configuracoes = configuracoes.order_by(ordenacoes.get(ordenar, "-atualizado_em"))
    page_obj = paginate_queryset(request, configuracoes, per_page=10)
    return render(
        request,
        "relatorios/configuracao_lista.html",
        {
            "configuracoes": page_obj,
            "page_obj": page_obj,
            "busca": busca,
            "ativo": ativo,
            "sort": ordenar,
        },
    )


def obter_configuracao_ativa(user):
    return queryset_da_empresa(ConfiguracaoEmpresa.objects.filter(ativo=True), user).order_by("-atualizado_em").first()


def obter_configuracao_do_orcamento(orcamento, user):
    if getattr(orcamento, "configuracao_empresa_id", None):
        configuracao_vinculada = queryset_da_empresa(ConfiguracaoEmpresa.objects.all(), user).filter(
            pk=orcamento.configuracao_empresa_id
        ).first()
        if configuracao_vinculada:
            return configuracao_vinculada
    return obter_configuracao_ativa(user)


@require_capability("pode_gerenciar_relatorios")
def configuracao_criar(request):
    if request.method == "POST":
        form = ConfiguracaoEmpresaForm(request.POST, request.FILES)
        if form.is_valid():
            configuracao = form.save(commit=False)
            configuracao.empresa = obter_grupo_empresa_ou_erro(request.user)
            configuracao.save()
            return redirect("relatorios:configuracao_lista")
    else:
        form = ConfiguracaoEmpresaForm()

    return render(
        request,
        "relatorios/configuracao_form.html",
        {"form": form, "titulo": "Nova configuração da empresa"},
    )


@require_capability("pode_visualizar_relatorios")
def configuracao_visualizar(request, pk):
    configuracao = get_object_or_404(queryset_da_empresa(ConfiguracaoEmpresa.objects.all(), request.user), pk=pk)
    form = ConfiguracaoEmpresaForm(instance=configuracao)
    return render(
        request,
        "relatorios/configuracao_form.html",
        {
            "form": form,
            "titulo": "Configuração da empresa",
            "configuracao": configuracao,
            "somente_leitura": True,
        },
    )


@require_capability("pode_visualizar_relatorios")
def configuracao_logo(request, pk):
    configuracao = get_object_or_404(
        queryset_da_empresa(ConfiguracaoEmpresa.objects.filter(ativo=True), request.user),
        pk=pk,
    )
    if not configuracao.logo:
        raise Http404
    try:
        arquivo = configuracao.logo.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc

    tipo_conteudo, _ = guess_type(configuracao.logo.name or "")
    response = FileResponse(arquivo, content_type=tipo_conteudo or "application/octet-stream")
    response["Cache-Control"] = "private, max-age=300"
    return response


@require_capability("pode_gerenciar_relatorios")
def configuracao_editar(request, pk):
    configuracao = get_object_or_404(queryset_da_empresa(ConfiguracaoEmpresa.objects.all(), request.user), pk=pk)

    if request.method == "POST":
        form = ConfiguracaoEmpresaForm(request.POST, request.FILES, instance=configuracao)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Dados da empresa atualizados. Os relatórios e os orçamentos ainda não enviados passam a usar essas informações.",
            )
            return redirect("relatorios:configuracao_lista")
    else:
        form = ConfiguracaoEmpresaForm(instance=configuracao)

    return render(
        request,
        "relatorios/configuracao_form.html",
        {"form": form, "titulo": "Editar configuração da empresa", "configuracao": configuracao},
    )


@require_capability("pode_gerenciar_relatorios")
def configuracao_excluir(request, pk):
    configuracao = get_object_or_404(queryset_da_empresa(ConfiguracaoEmpresa.objects.all(), request.user), pk=pk)
    acao = "reativar" if not configuracao.ativo else "inativar"

    if request.method == "POST":
        configuracao.ativo = not configuracao.ativo
        configuracao.save(update_fields=["ativo", "atualizado_em"])
        if configuracao.ativo:
            messages.success(request, "Configuração reativada com sucesso.")
        else:
            messages.success(request, "Configuração inativada com sucesso.")
        return redirect("relatorios:configuracao_lista")

    return render(
        request,
        "relatorios/configuracao_excluir.html",
        {"configuracao": configuracao, "acao": acao},
    )


@require_capability("pode_visualizar_orcamentos")
def orcamento_relatorio_central(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user),
        pk=pk,
    )
    if request.method == "POST":
        if not request.user.pode_gerenciar_orcamentos:
            raise PermissionDenied
        campos_opcoes = [
            "mostrar_ajustes_no_relatorio",
            "mostrar_descricao_inicial_no_relatorio",
            "mostrar_observacoes_gerais_no_relatorio",
            "mostrar_rodape_institucional_no_relatorio",
            "mostrar_contatos_evento_no_memorial",
            "mostrar_financeiro_no_memorial",
            "mostrar_dados_contratuais_no_memorial",
            "mostrar_informacoes_complementares_no_memorial",
        ]
        for campo in campos_opcoes:
            setattr(orcamento, campo, request.POST.get(campo) == "on")
        orcamento.save(update_fields=[*campos_opcoes, "atualizado_em"])
        messages.success(request, "Opções do relatório atualizadas.")
        return redirect("relatorios:orcamento_central", pk=orcamento.pk)
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    alerta_status = obter_alerta_status(orcamento)
    return render(
        request,
        "relatorios/orcamento_central.html",
        {
            "orcamento": orcamento,
            "configuracao": configuracao,
            "alerta_status": alerta_status,
            "subtotais_categoria": orcamento.subtotais_por_categoria(),
        },
    )


@require_capability("pode_visualizar_orcamentos")
def orcamento_exportar_excel(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user),
        pk=pk,
    )
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    alerta_status = obter_alerta_status(orcamento)
    conteudo = gerar_excel_orcamento(orcamento, configuracao, alerta_status)

    response = HttpResponse(conteudo, content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = f'attachment; filename="orcamento-{orcamento.numero}.xls"'
    return response


@require_capability("pode_visualizar_orcamentos")
def orcamento_exportar_pdf(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user),
        pk=pk,
    )
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    alerta_status = obter_alerta_status(orcamento)
    conteudo = gerar_pdf_orcamento(orcamento, configuracao, alerta_status)

    response = HttpResponse(conteudo, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="orcamento-{orcamento.numero}.pdf"'
    return response


@require_capability("pode_visualizar_orcamentos")
def orcamento_exportar_memorial_pdf(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user),
        pk=pk,
    )
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    conteudo = gerar_pdf_memorial_descritivo(orcamento, configuracao)

    response = HttpResponse(conteudo, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="memorial-descritivo-{orcamento.numero}.pdf"'
    return response


@require_capability("pode_visualizar_orcamentos")
def orcamento_exportar_memorial_word(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user),
        pk=pk,
    )
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    conteudo = gerar_word_memorial_descritivo(orcamento, configuracao)

    response = HttpResponse(conteudo, content_type="application/rtf")
    response["Content-Disposition"] = f'attachment; filename="memorial-descritivo-{orcamento.numero}.rtf"'
    return response
