from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Dados pessoais", {"fields": ("first_name", "last_name", "email", "nome_exibicao")}),
        ("Acesso", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Datas", {"fields": ("last_login", "date_joined", "criado_em", "atualizado_em")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2", "is_active", "is_staff", "is_superuser"),
            },
        ),
    )
    readonly_fields = ("criado_em", "atualizado_em")
    list_display = ("username", "email", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")
    filter_horizontal = ()

    def get_queryset(self, request):
        return super().get_queryset(request)

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_staff and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

# Register your models here.
