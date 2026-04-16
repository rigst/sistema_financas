from django.contrib import admin

from core.admin_permissions import PerfilAdminPermissionMixin

from .models import Despesa, Receita, Reserva


class FinanceiroAdminMixin(PerfilAdminPermissionMixin):
    capability_view = "pode_visualizar_financeiro"
    capability_add = "pode_gerenciar_financeiro"
    capability_change = "pode_gerenciar_financeiro"
    capability_delete = "pode_gerenciar_financeiro"


@admin.register(Receita)
class ReceitaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("descricao", "valor", "data", "categoria", "status", "empresa")
    list_filter = ("status", "empresa", "data")
    search_fields = ("descricao", "categoria", "observacoes")
    date_hierarchy = "data"


@admin.register(Despesa)
class DespesaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("descricao", "tipo", "valor", "data", "categoria", "parcelas", "status", "empresa")
    list_filter = ("tipo", "status", "empresa", "data")
    search_fields = ("descricao", "categoria", "observacoes")
    date_hierarchy = "data"


@admin.register(Reserva)
class ReservaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "valor_atual", "valor_alvo", "empresa")
    list_filter = ("empresa",)
    search_fields = ("nome", "observacoes")
