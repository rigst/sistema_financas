from django.contrib import admin

from core.admin_permissions import PerfilAdminPermissionMixin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(PerfilAdminPermissionMixin, admin.ModelAdmin):
    capability_view = "pode_visualizar_clientes"
    capability_add = "pode_gerenciar_clientes"
    capability_change = "pode_gerenciar_clientes"
    capability_delete = "pode_gerenciar_clientes"
    list_display = (
        "nome_razao_social",
        "tipo_pessoa",
        "cpf_cnpj",
        "email",
        "telefone",
        "ativo",
    )
    list_filter = ("tipo_pessoa", "ativo")
    search_fields = ("nome_razao_social", "nome_fantasia", "cpf_cnpj", "email")
    ordering = ("nome_razao_social",)

# Register your models here.
