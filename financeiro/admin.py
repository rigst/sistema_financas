from django.contrib import admin

from core.admin_permissions import PerfilAdminPermissionMixin

from .models import Despesa, MentoriaFinanceiraIA, Receita, Reserva


class FinanceiroAdminMixin(PerfilAdminPermissionMixin):
    pass


@admin.register(Receita)
class ReceitaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    exclude = ("criado_por",)
    list_display = ("descricao", "valor", "data", "categoria", "status")
    list_filter = ("status", "data")
    search_fields = ("descricao", "categoria", "observacoes")
    date_hierarchy = "data"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Despesa)
class DespesaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    exclude = ("criado_por",)
    list_display = ("descricao", "tipo", "valor", "valor_parcela", "data", "categoria", "parcelas", "status")
    list_filter = ("tipo", "status", "data")
    search_fields = ("descricao", "categoria", "observacoes")
    date_hierarchy = "data"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Reserva)
class ReservaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    exclude = ("criado_por",)
    list_display = ("nome", "valor_atual", "valor_alvo", "percentual_concluido")
    search_fields = ("nome", "observacoes")

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


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
