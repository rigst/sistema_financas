from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission


class UsuarioModelBackend(ModelBackend):
    """Backend de autenticação compatível com o `Usuario` deste projeto.

    O modelo remove as relações `groups` e `user_permissions` (atribui `None` a
    elas), porque aqui a autorização é decidida por `is_staff`/`is_superuser` e
    pelos mixins de admin — não pelo sistema de permissões do Django.

    O `ModelBackend` padrão, porém, chama `user_obj.user_permissions.all()` ao
    resolver `has_perm()`, o que rebenta com `AttributeError` em `None`. A falha
    é latente desde que os campos foram removidos: só não aparecia porque o admin
    nativo curto-circuitava as permissões nos mixins antes de consultá-las. Aqui
    as duas consultas passam a devolver conjunto vazio, e a decisão continua
    sendo do `is_superuser` (que o ModelBackend trata à parte) e dos mixins.
    """

    def _get_user_permissions(self, user_obj):
        return Permission.objects.none()

    def _get_group_permissions(self, user_obj):
        return Permission.objects.none()
