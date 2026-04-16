from django.contrib import admin
from django.contrib.auth.models import Group

from core.tenancy import VISITOR_GROUP_PREFIX, obter_grupo_empresa_usuario
from .models import Empresa


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(Group)
class EmpresaGroupAdmin(admin.ModelAdmin):
    fields = ("name",)
    list_display = ("name",)
    search_fields = ("name",)

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return bool(request.user.is_active and request.user.is_staff and getattr(request.user, "eh_admin_perfil", False))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).exclude(name__startswith=VISITOR_GROUP_PREFIX)
        grupo = obter_grupo_empresa_usuario(request.user)
        if request.user.is_superuser:
            return queryset
        if grupo is None:
            return queryset.none()
        return queryset.filter(pk=grupo.pk)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "name" in form.base_fields:
            form.base_fields["name"].label = "Empresa"
            form.base_fields["name"].help_text = "Cada grupo representa uma empresa isolada das demais no sistema."
        return form


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "grupo", "ativa", "atualizada_em")
    list_filter = ("ativa",)
    search_fields = ("nome", "grupo__name")
    readonly_fields = ("criada_em", "atualizada_em")

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return bool(request.user.is_active and request.user.is_staff and getattr(request.user, "eh_admin_perfil", False))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        queryset = super().get_queryset(request).exclude(grupo__name__startswith=VISITOR_GROUP_PREFIX)
        grupo = obter_grupo_empresa_usuario(request.user)
        if request.user.is_superuser:
            return queryset
        if grupo is None:
            return queryset.none()
        return queryset.filter(grupo=grupo)
