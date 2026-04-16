from django.contrib import admin

from core.admin_permissions import PerfilAdminPermissionMixin
from .models import CategoriaItem, ItemCatalogo


@admin.register(CategoriaItem)
class CategoriaItemAdmin(PerfilAdminPermissionMixin, admin.ModelAdmin):
    capability_view = "pode_visualizar_catalogo"
    capability_add = "pode_gerenciar_catalogo"
    capability_change = "pode_gerenciar_catalogo"
    capability_delete = "pode_gerenciar_catalogo"
    list_display = ("nome", "ativo", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("nome",)
    ordering = ("nome",)


@admin.register(ItemCatalogo)
class ItemCatalogoAdmin(PerfilAdminPermissionMixin, admin.ModelAdmin):
    capability_view = "pode_visualizar_catalogo"
    capability_add = "pode_gerenciar_catalogo"
    capability_change = "pode_gerenciar_catalogo"
    capability_delete = "pode_gerenciar_catalogo"
    list_display = (
        "codigo",
        "nome",
        "categoria",
        "unidade_medida",
        "valor_unitario_padrao",
        "ativo",
    )
    list_filter = ("ativo", "categoria", "unidade_medida")
    search_fields = ("codigo", "nome", "descricao_padrao")
    ordering = ("nome",)
