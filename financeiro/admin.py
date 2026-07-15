from django.contrib import admin

from core.admin_permissions import PerfilAdminPermissionMixin

from .models import (
    CompartilhamentoDespesa,
    Despesa,
    MentoriaFinanceiraIA,
    PagamentoDespesa,
    ParticipanteCompartilhamentoDespesa,
    Receita,
    RecebimentoReceita,
    Reserva,
)


class FinanceiroAdminMixin(PerfilAdminPermissionMixin):
    pass


class FinanceiroInlineAdminMixin(PerfilAdminPermissionMixin):
    def has_add_permission(self, request, obj=None):
        return self._has_admin_access(request)


class RecebimentoReceitaInline(FinanceiroInlineAdminMixin, admin.TabularInline):
    model = RecebimentoReceita
    extra = 0


class PagamentoDespesaInline(FinanceiroInlineAdminMixin, admin.TabularInline):
    model = PagamentoDespesa
    extra = 0


@admin.register(Receita)
class ReceitaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    exclude = ("criado_por",)
    list_display = ("descricao", "tipo", "valor", "data", "competencia", "categoria", "parcelas", "parcela_atual", "status", "ativa")
    list_filter = ("tipo", "status", "ativa", "competencia", "data")
    search_fields = ("descricao", "categoria", "observacoes")
    date_hierarchy = "data"
    inlines = (RecebimentoReceitaInline,)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Despesa)
class DespesaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    exclude = ("criado_por",)
    list_display = ("descricao", "tipo", "valor", "valor_parcela", "data", "competencia", "categoria", "parcelas", "parcela_atual", "status")
    list_filter = ("tipo", "competencia", "data", "status")
    search_fields = ("descricao", "categoria", "observacoes")
    date_hierarchy = "data"
    inlines = (PagamentoDespesaInline,)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Reserva)
class ReservaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    exclude = ("criado_por",)
    list_display = ("nome", "valor_atual", "valor_alvo", "percentual_concluido", "ativa")
    list_filter = ("ativa",)
    search_fields = ("nome", "observacoes")

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


class ParticipanteCompartilhamentoDespesaInline(admin.TabularInline):
    model = ParticipanteCompartilhamentoDespesa
    extra = 0
    autocomplete_fields = ("usuario", "despesa_gerada")
    readonly_fields = ("data_aceite", "data_confirmacao_ressarcimento")


@admin.register(CompartilhamentoDespesa)
class CompartilhamentoDespesaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("despesa", "valor_total", "modo_divisao", "pagador", "data_prevista_ressarcimento", "criado_por")
    list_filter = ("modo_divisao", "data_prevista_ressarcimento")
    search_fields = ("despesa__descricao", "criado_por__username", "pagador__username")
    autocomplete_fields = ("despesa", "criado_por", "pagador")
    inlines = (ParticipanteCompartilhamentoDespesaInline,)


@admin.register(MentoriaFinanceiraIA)
class MentoriaFinanceiraIAAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("periodo_inicio", "periodo_fim", "modelo", "criado_em")
    readonly_fields = ("criado_por", "periodo_inicio", "periodo_fim", "conteudo", "dados_enviados", "modelo", "criado_em")
    search_fields = ("conteudo", "modelo")
    date_hierarchy = "criado_em"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
