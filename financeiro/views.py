import csv
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
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
from .models import (
    CompartilhamentoDespesa,
    Despesa,
    PagamentoDespesa,
    ParticipanteCompartilhamentoDespesa,
    Receita,
    RecebimentoReceita,
    Reserva,
    arredondar,
)
from .planejamento import calcular_planejamento_semanal, navegacao_semanal


def _queryset_simples(modelo, request):
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    mostrar_inativos = request.GET.get("inativos") == "1"
    itens = modelo.objects.filter(criado_por=request.user)
    if modelo is Receita and not mostrar_inativos:
        itens = itens.filter(ativa=True)
    if modelo is Despesa and not mostrar_inativos:
        itens = itens.exclude(status="cancelada")
    status_validos = {choice[0] for choice in getattr(modelo, "STATUS_CHOICES", [])}
    if status in status_validos:
        itens = itens.filter(status=status)
    if busca:
        itens = filter_ranked_search(itens, busca, ("descricao", "observacoes", "categoria"))
    return itens, busca, status, mostrar_inativos


def _voltar_para(request, fallback):
    destino = request.POST.get("next") or request.GET.get("next") or reverse(fallback)
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(fallback)


def _referencia_semanal(request):
    return parse_date(request.GET.get("semana", "")) or timezone.localdate()


def _parse_competencia(valor):
    texto = (valor or "").strip()
    if len(texto) == 7:
        texto = f"{texto}-01"
    data = parse_date(texto)
    return data.replace(day=1) if data else None


def _competencia_do_post(request):
    return _parse_competencia(request.POST.get("competencia")) or timezone.localdate().replace(day=1)


def _obter_compartilhamento(despesa):
    try:
        return despesa.compartilhamento
    except CompartilhamentoDespesa.DoesNotExist:
        return None


def _sincronizar_pagamentos_compartilhados(origem, gerada):
    if origem.tipo == "variavel" or gerada.status == "cancelada":
        return
    pagamentos_origem = {item.competencia: item.data_pagamento for item in origem.pagamentos.all()}
    gerada.pagamentos.exclude(competencia__in=pagamentos_origem.keys()).delete()
    existentes = set(gerada.pagamentos.values_list("competencia", flat=True))
    PagamentoDespesa.objects.bulk_create(
        [
            PagamentoDespesa(despesa=gerada, competencia=competencia, data_pagamento=data_pagamento)
            for competencia, data_pagamento in pagamentos_origem.items()
            if competencia not in existentes
        ]
    )


def _sincronizar_despesa_compartilhada(participante):
    origem = participante.compartilhamento.despesa
    if participante.status != "aceito" or not participante.compartilhamento.pronto_para_computar:
        if participante.despesa_gerada:
            participante.despesa_gerada.status = "cancelada"
            participante.despesa_gerada.save(update_fields=["status", "atualizado_em"])
        return
    dados = {
        "tipo": origem.tipo,
        "descricao": origem.descricao,
        "valor": participante.valor,
        "data": origem.data,
        "competencia": origem.competencia,
        "data_fim": origem.data_fim,
        "categoria": origem.categoria,
        "parcelas": origem.parcelas,
        "parcela_atual": origem.parcela_atual,
        "status": origem.status if origem.status != "cancelada" else "cancelada",
        "observacoes": origem.observacoes,
        "criado_por": participante.usuario,
    }
    if participante.despesa_gerada_id:
        despesa = participante.despesa_gerada
        for campo, valor in dados.items():
            setattr(despesa, campo, valor)
        despesa.save()
    else:
        participante.despesa_gerada = Despesa.objects.create(**dados)
        participante.save(update_fields=["despesa_gerada", "atualizado_em"])
    _sincronizar_pagamentos_compartilhados(origem, participante.despesa_gerada)


def _sincronizar_participantes_compartilhamento(despesa):
    compartilhamento = _obter_compartilhamento(despesa)
    if not compartilhamento:
        return
    for participante in compartilhamento.participantes.filter(status="aceito").select_related("despesa_gerada", "usuario"):
        _sincronizar_despesa_compartilhada(participante)


def _status_compartilhamento(compartilhamento):
    return compartilhamento.status_geral


def _salvar_compartilhamento_despesa(despesa, form, user):
    compartilhar = form.cleaned_data.get("compartilhar")
    compartilhamento = _obter_compartilhamento(despesa)
    if not compartilhar:
        if compartilhamento:
            for participante in compartilhamento.participantes.filter(status="aceito").select_related("despesa_gerada"):
                if participante.despesa_gerada:
                    participante.despesa_gerada.status = "cancelada"
                    participante.despesa_gerada.save(update_fields=["status", "atualizado_em"])
            compartilhamento.delete()
        return

    valor_total = form.cleaned_data["valor"]
    despesa.valor = form.cleaned_data["valor_criador_compartilhado"]
    despesa.save(update_fields=["valor", "atualizado_em"])
    compartilhamento, _created = CompartilhamentoDespesa.objects.update_or_create(
        despesa=despesa,
        defaults={
            "criado_por": user,
            "valor_total": valor_total,
            "modo_divisao": form.cleaned_data.get("modo_divisao") or "igual",
            "pagador": form.cleaned_data["pagador_resolvido"],
            "recusado_por": None,
            "data_prevista_ressarcimento": form.cleaned_data.get("data_prevista_ressarcimento"),
        },
    )
    participantes_form = dict(form.cleaned_data["participantes_resolvidos"])
    ids_atuais = []
    for usuario, valor in participantes_form.items():
        participante, _created = ParticipanteCompartilhamentoDespesa.objects.update_or_create(
            compartilhamento=compartilhamento,
            usuario=usuario,
            defaults={"valor": valor},
        )
        if participante.status == "recusado":
            participante.status = "pendente"
            participante.ressarcimento_confirmado = False
            participante.data_aceite = None
            participante.data_confirmacao_ressarcimento = None
            participante.save(
                update_fields=[
                    "status",
                    "ressarcimento_confirmado",
                    "data_aceite",
                    "data_confirmacao_ressarcimento",
                    "atualizado_em",
                ]
            )
        ids_atuais.append(participante.pk)
        _sincronizar_despesa_compartilhada(participante)
    removidos = compartilhamento.participantes.exclude(pk__in=ids_atuais)
    for participante in removidos.select_related("despesa_gerada"):
        if participante.despesa_gerada:
            participante.despesa_gerada.status = "cancelada"
            participante.despesa_gerada.save(update_fields=["status", "atualizado_em"])
    removidos.delete()


def _anotar_referencia_mensal(itens, hoje, modelo_registro, campo_fk):
    """Anota itens de série (fixa/parcelada) com a competência de referência e se ela está quitada."""
    series_ids = [item.pk for item in itens if item.tipo != "variavel"]
    quitadas = (
        set(modelo_registro.objects.filter(**{f"{campo_fk}_id__in": series_ids}).values_list(f"{campo_fk}_id", "competencia"))
        if series_ids
        else set()
    )
    for item in itens:
        if item.tipo == "variavel":
            item.competencia_ref = None
            item.quitada_na_referencia = False
        else:
            item.competencia_ref = item.competencia_de_referencia(hoje)
            item.quitada_na_referencia = (item.pk, item.competencia_ref) in quitadas


@login_required
def receita_lista(request):
    receitas, busca, status, mostrar_inativos = _queryset_simples(Receita, request)
    page_obj = paginate_queryset(request, receitas, per_page=25)
    hoje = timezone.localdate()
    for item in page_obj.object_list:
        item.parcela_exibicao = item.parcela_na_data(hoje) if item.tipo == "parcelada" else None
    _anotar_referencia_mensal(page_obj.object_list, hoje, RecebimentoReceita, "receita")
    return render(
        request,
        "financeiro/receita_lista.html",
        {"receitas": page_obj, "page_obj": page_obj, "busca": busca, "status": status, "mostrar_inativos": mostrar_inativos},
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
    receita = get_object_or_404(Receita.objects.filter(criado_por=request.user, ativa=True), pk=pk)
    if receita.tipo == "variavel":
        receita.status = "recebida"
        receita.data_recebimento = timezone.localdate()
        receita.save(update_fields=["status", "data_recebimento", "atualizado_em"])
        messages.success(request, "Receita marcada como recebida.")
    else:
        competencia = _competencia_do_post(request)
        if not receita.competencia_valida(competencia):
            messages.error(request, "Competência fora do período desta receita.")
            return _voltar_para(request, "financeiro:receita_lista")
        RecebimentoReceita.objects.get_or_create(
            receita=receita,
            competencia=competencia,
            defaults={"data_recebimento": timezone.localdate()},
        )
        messages.success(request, f"Receita marcada como recebida em {competencia:%m/%Y}.")
    return _voltar_para(request, "financeiro:receita_lista")


@require_POST
@login_required
def receita_desmarcar_recebida(request, pk):
    receita = get_object_or_404(Receita.objects.filter(criado_por=request.user, ativa=True), pk=pk)
    if receita.tipo == "variavel":
        receita.status = "prevista"
        receita.data_recebimento = None
        receita.save(update_fields=["status", "data_recebimento", "atualizado_em"])
        messages.success(request, "Receita marcada como prevista.")
    else:
        competencia = _competencia_do_post(request)
        RecebimentoReceita.objects.filter(receita=receita, competencia=competencia).delete()
        messages.success(request, f"Recebimento de {competencia:%m/%Y} desfeito.")
    return _voltar_para(request, "financeiro:receita_lista")


@require_POST
@login_required
def receita_excluir(request, pk):
    receita = get_object_or_404(Receita.objects.filter(criado_por=request.user), pk=pk)
    receita.ativa = False
    receita.save(update_fields=["ativa", "atualizado_em"])
    messages.success(request, "Receita inativada.")
    return _voltar_para(request, "financeiro:receita_lista")


@login_required
def despesa_lista(request):
    despesas, busca, _status, mostrar_inativos = _queryset_simples(Despesa, request)
    tipo = request.GET.get("tipo", "").strip()
    compartilhamento_filtro = request.GET.get("compartilhamento", "").strip()
    tipos_validos = {choice[0] for choice in Despesa.TIPO_CHOICES}
    if tipo in tipos_validos:
        despesas = despesas.filter(tipo=tipo)
    filtrar_compartilhadas = compartilhamento_filtro == "compartilhadas"
    if filtrar_compartilhadas:
        despesas = despesas.filter(Q(compartilhamento__isnull=False) | Q(participacao_compartilhada__isnull=False)).distinct()
    fixas = Despesa.objects.filter(criado_por=request.user, tipo="fixa").exclude(status="cancelada")
    parceladas_qs = Despesa.objects.filter(criado_por=request.user, tipo="parcelada").exclude(status="cancelada")
    if filtrar_compartilhadas:
        fixas = fixas.filter(Q(compartilhamento__isnull=False) | Q(participacao_compartilhada__isnull=False)).distinct()
        parceladas_qs = parceladas_qs.filter(Q(compartilhamento__isnull=False) | Q(participacao_compartilhada__isnull=False)).distinct()
    fixas = [item for item in fixas.order_by("-valor", "descricao") if item.deve_computar()]
    parceladas = list(parceladas_qs.order_by("descricao"))
    page_obj = paginate_queryset(request, despesas, per_page=25)
    hoje = timezone.localdate()
    parceladas.sort(key=lambda item: (item.valor_parcela, item.valor), reverse=True)
    for item in parceladas:
        item.parcela_exibicao = item.parcela_na_data(hoje)
    parceladas = [item for item in parceladas if item.deve_computar()]
    for item in page_obj.object_list:
        item.parcela_exibicao = item.parcela_na_data(hoje) if item.tipo == "parcelada" else None
        item.compartilhamento_info = _obter_compartilhamento(item)
        try:
            item.participacao_info = item.participacao_compartilhada
        except ParticipanteCompartilhamentoDespesa.DoesNotExist:
            item.participacao_info = None
    _anotar_referencia_mensal(page_obj.object_list, hoje, PagamentoDespesa, "despesa")
    compartilhadas_recebidas = (
        ParticipanteCompartilhamentoDespesa.objects.filter(usuario=request.user)
        .filter(Q(status="pendente") | Q(status="recusado") | Q(status="aceito", ressarcimento_confirmado=False))
        .select_related("compartilhamento__despesa", "compartilhamento__criado_por", "compartilhamento__pagador", "compartilhamento__recusado_por", "despesa_gerada")
        .order_by("status", "-criado_em")
    )
    compartilhadas_criadas = (
        CompartilhamentoDespesa.objects.filter(criado_por=request.user)
        .exclude(despesa__status="cancelada")
        .select_related("despesa", "pagador", "recusado_por")
        .prefetch_related("participantes__usuario")
    )
    compartilhadas_alertas_count = len(compartilhadas_recebidas) + sum(
        1 for compartilhamento in compartilhadas_criadas if compartilhamento.status_geral != "aceito"
    )
    return render(
        request,
        "financeiro/despesa_lista.html",
        {
            "despesas": page_obj,
            "page_obj": page_obj,
            "busca": busca,
            "tipo": tipo,
            "compartilhamento_filtro": compartilhamento_filtro,
            "fixas": fixas,
            "parceladas": parceladas,
            "hoje": hoje,
            "mostrar_inativos": mostrar_inativos,
            "compartilhadas_recebidas": compartilhadas_recebidas,
            "compartilhadas_criadas": compartilhadas_criadas,
            "compartilhadas_alertas_count": compartilhadas_alertas_count,
        },
    )


@login_required
def despesa_criar(request):
    if request.method == "POST":
        form = DespesaSimplificadaForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                despesa = form.save(commit=False)
                despesa.criado_por = request.user
                despesa.save()
                _salvar_compartilhamento_despesa(despesa, form, request.user)
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
            with transaction.atomic():
                despesa = form.save()
                _salvar_compartilhamento_despesa(despesa, form, request.user)
            messages.success(request, "Despesa atualizada com sucesso.")
            return redirect("financeiro:despesa_lista")
    else:
        form = DespesaSimplificadaForm(instance=despesa, user=request.user)
    return render(request, "financeiro/despesa_form.html", {"form": form, "titulo": "Editar despesa"})


@require_POST
@login_required
def despesa_marcar_paga(request, pk):
    despesa = get_object_or_404(Despesa.objects.filter(criado_por=request.user).exclude(status="cancelada"), pk=pk)
    if despesa.tipo == "variavel":
        despesa.status = "paga"
        despesa.save(update_fields=["status", "atualizado_em"])
        messages.success(request, "Despesa marcada como paga.")
    else:
        competencia = _competencia_do_post(request)
        if not despesa.competencia_valida(competencia):
            messages.error(request, "Competência fora do período desta despesa.")
            return _voltar_para(request, "financeiro:despesa_lista")
        PagamentoDespesa.objects.get_or_create(
            despesa=despesa,
            competencia=competencia,
            defaults={"data_pagamento": timezone.localdate()},
        )
        messages.success(request, f"Despesa marcada como paga em {competencia:%m/%Y}.")
    _sincronizar_participantes_compartilhamento(despesa)
    return _voltar_para(request, "financeiro:despesa_lista")


@require_POST
@login_required
def despesa_desmarcar_paga(request, pk):
    despesa = get_object_or_404(Despesa.objects.filter(criado_por=request.user).exclude(status="cancelada"), pk=pk)
    if despesa.tipo == "variavel":
        despesa.status = "pendente"
        despesa.save(update_fields=["status", "atualizado_em"])
        messages.success(request, "Despesa marcada como pendente.")
    else:
        competencia = _competencia_do_post(request)
        PagamentoDespesa.objects.filter(despesa=despesa, competencia=competencia).delete()
        messages.success(request, f"Pagamento de {competencia:%m/%Y} desfeito.")
    _sincronizar_participantes_compartilhamento(despesa)
    return _voltar_para(request, "financeiro:despesa_lista")


@require_POST
@login_required
def despesa_cancelar(request, pk):
    despesa = get_object_or_404(Despesa.objects.filter(criado_por=request.user), pk=pk)
    despesa.status = "cancelada"
    despesa.save(update_fields=["status", "atualizado_em"])
    _sincronizar_participantes_compartilhamento(despesa)
    messages.success(request, "Despesa cancelada.")
    return _voltar_para(request, "financeiro:despesa_lista")


@login_required
def despesas_compartilhadas(request):
    return redirect("financeiro:despesa_lista")


@require_POST
@login_required
def despesa_compartilhada_aceitar(request, pk):
    participante = get_object_or_404(ParticipanteCompartilhamentoDespesa.objects.filter(usuario=request.user), pk=pk)
    if participante.status != "aceito":
        participante.status = "aceito"
        participante.data_aceite = timezone.now()
        participante.save(update_fields=["status", "data_aceite", "atualizado_em"])
    _sincronizar_participantes_compartilhamento(participante.compartilhamento.despesa)
    messages.success(request, "Despesa compartilhada aceita.")
    return _voltar_para(request, "financeiro:despesa_lista")


@require_POST
@login_required
def despesa_compartilhada_recusar(request, pk):
    participante = get_object_or_404(ParticipanteCompartilhamentoDespesa.objects.filter(usuario=request.user), pk=pk)
    compartilhamento = participante.compartilhamento
    compartilhamento.recusado_por = request.user
    compartilhamento.save(update_fields=["recusado_por", "atualizado_em"])
    for item in compartilhamento.participantes.select_related("despesa_gerada"):
        item.status = "recusado"
        item.ressarcimento_confirmado = False
        item.save(update_fields=["status", "ressarcimento_confirmado", "atualizado_em"])
        if item.despesa_gerada:
            item.despesa_gerada.status = "cancelada"
            item.despesa_gerada.save(update_fields=["status", "atualizado_em"])
    messages.success(request, "Despesa compartilhada recusada.")
    return _voltar_para(request, "financeiro:despesa_lista")


@require_POST
@login_required
def despesa_compartilhada_confirmar_ressarcimento(request, pk):
    participante = get_object_or_404(ParticipanteCompartilhamentoDespesa.objects.filter(usuario=request.user, status="aceito"), pk=pk)
    participante.ressarcimento_confirmado = True
    participante.data_confirmacao_ressarcimento = timezone.now()
    participante.save(update_fields=["ressarcimento_confirmado", "data_confirmacao_ressarcimento", "atualizado_em"])
    messages.success(request, "Ressarcimento confirmado.")
    return _voltar_para(request, "financeiro:despesa_lista")


@login_required
def exportar_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="financeiro_simplificado.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["tipo", "descricao", "valor", "data", "competencia", "categoria", "status", "parcelas", "parcela_atual", "observacoes"])

    receitas = Receita.objects.filter(criado_por=request.user).order_by("data", "id")
    despesas = Despesa.objects.filter(criado_por=request.user).order_by("data", "id")
    for item in receitas:
        writer.writerow(
            [
                "receita",
                item.descricao,
                item.valor,
                item.data.isoformat(),
                item.competencia.strftime("%Y-%m"),
                item.categoria,
                item.get_status_display(),
                item.parcelas,
                item.parcela_atual,
                item.observacoes,
            ]
        )
    for item in despesas:
        writer.writerow(
            [
                "despesa",
                item.descricao,
                item.valor,
                item.data.isoformat(),
                item.competencia.strftime("%Y-%m"),
                item.categoria,
                item.get_status_display(),
                item.parcelas,
                item.parcela_atual,
                item.observacoes,
            ]
        )
    return response


@login_required
def controle(request):
    referencia = _referencia_semanal(request)
    mostrar_inativos = request.GET.get("inativos") == "1"
    planejamento = calcular_planejamento_semanal(request.user, referencia, quantidade=6)
    reservas = Reserva.objects.filter(criado_por=request.user)
    if not mostrar_inativos:
        reservas = reservas.filter(ativa=True)
    fixas = Despesa.objects.filter(criado_por=request.user, tipo="fixa").exclude(status="cancelada").order_by("descricao")
    reservas_total = arredondar(sum((reserva.valor_atual for reserva in reservas.filter(ativa=True)), Decimal("0.00")))
    return render(
        request,
        "financeiro/controle.html",
        {
            "planejamento": planejamento,
            "reservas": reservas,
            "fixas": fixas,
            "reservas_total": reservas_total,
            "semana_nav": navegacao_semanal(referencia),
            "mostrar_inativos": mostrar_inativos,
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


@require_POST
@login_required
def reserva_excluir(request, pk):
    reserva = get_object_or_404(Reserva.objects.filter(criado_por=request.user), pk=pk)
    reserva.ativa = False
    reserva.save(update_fields=["ativa", "atualizado_em"])
    messages.success(request, "Meta inativada.")
    return _voltar_para(request, "financeiro:controle")
