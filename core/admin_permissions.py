class PerfilAdminPermissionMixin:
    def _has_admin_access(self, request):
        return bool(request.user.is_active and request.user.is_staff)

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def has_view_permission(self, request, obj=None):
        return self._has_admin_access(request)

    def has_add_permission(self, request):
        return self._has_admin_access(request)

    def has_change_permission(self, request, obj=None):
        return self._has_admin_access(request)

    def has_delete_permission(self, request, obj=None):
        return self._has_admin_access(request)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if hasattr(queryset.model, "criado_por_id"):
            return queryset.filter(criado_por=request.user)
        return queryset
