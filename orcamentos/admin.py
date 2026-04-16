from django.contrib import admin

from core.admin_permissions import PerfilAdminPermissionMixin
from .models import ItemOrcamento, Orcamento


class ItemOrcamentoInline(PerfilAdminPermissionMixin, admin.TabularInline):
    model = ItemOrcamento
    extra = 1
    capability_view = "pode_visualizar_orcamentos"
    capability_add = "pode_gerenciar_orcamentos"
    capability_change = "pode_gerenciar_orcamentos"
    capability_delete = "pode_gerenciar_orcamentos"


@admin.register(Orcamento)
class OrcamentoAdmin(PerfilAdminPermissionMixin, admin.ModelAdmin):
    capability_view = "pode_visualizar_orcamentos"
    capability_add = "pode_gerenciar_orcamentos"
    capability_change = "pode_gerenciar_orcamentos"
    capability_delete = "pode_gerenciar_orcamentos"
    list_display = (
        "numero",
        "cliente",
        "ativo",
        "status",
        "data_emissao",
        "validade_em",
        "total_final",
        "mostrar_ajustes_no_relatorio",
    )
    list_filter = ("ativo", "status", "mostrar_ajustes_no_relatorio", "data_emissao")
    search_fields = ("numero", "cliente__nome_razao_social", "titulo")
    inlines = [ItemOrcamentoInline]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ItemOrcamento)
class ItemOrcamentoAdmin(PerfilAdminPermissionMixin, admin.ModelAdmin):
    capability_view = "pode_visualizar_orcamentos"
    capability_add = "pode_gerenciar_orcamentos"
    capability_change = "pode_gerenciar_orcamentos"
    capability_delete = "pode_gerenciar_orcamentos"
    list_display = (
        "orcamento",
        "ordem",
        "codigo_item",
        "nome",
        "quantidade",
        "valor_unitario",
        "subtotal",
    )
    list_filter = ("unidade_medida",)
    search_fields = ("orcamento__numero", "codigo_item", "nome")
