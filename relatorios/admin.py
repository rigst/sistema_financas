from django.contrib import admin

from core.admin_permissions import PerfilAdminPermissionMixin
from .models import ConfiguracaoEmpresa


@admin.register(ConfiguracaoEmpresa)
class ConfiguracaoEmpresaAdmin(PerfilAdminPermissionMixin, admin.ModelAdmin):
    capability_view = "pode_visualizar_relatorios"
    capability_add = "pode_gerenciar_relatorios"
    capability_change = "pode_gerenciar_relatorios"
    capability_delete = "pode_gerenciar_relatorios"
    list_display = ("nome_empresa", "email", "telefone", "cidade", "estado", "atualizado_em")
    search_fields = ("nome_empresa", "nome_fantasia", "cpf_cnpj", "email")
