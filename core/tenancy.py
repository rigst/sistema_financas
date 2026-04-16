from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

from core.models import Empresa


DEFAULT_EMPRESA_GROUP_NAME = "Empresa padrão"
VISITOR_GROUP_PREFIX = "__visitante__"
EMPRESA_ATIVA_SESSION_KEY = "empresa_ativa_id"


def obter_grupo_empresa_padrao():
    grupo, _ = Group.objects.get_or_create(name=DEFAULT_EMPRESA_GROUP_NAME)
    Empresa.objects.get_or_create(grupo=grupo, defaults={"nome": grupo.name, "ativa": True})
    return grupo


def _garantir_empresas_para_grupos(grupos):
    for grupo in grupos:
        Empresa.objects.get_or_create(grupo=grupo, defaults={"nome": grupo.name, "ativa": True})


def obter_empresas_usuario(user):
    if not getattr(user, "is_authenticated", False):
        return Empresa.objects.none()
    grupos = list(user.groups.order_by("name", "id"))
    if not grupos:
        return Empresa.objects.none()
    _garantir_empresas_para_grupos(grupos)
    grupo_ids = [grupo.pk for grupo in grupos]
    return Empresa.objects.filter(grupo_id__in=grupo_ids).order_by("nome", "id")


def obter_empresa_ativa_usuario(user):
    empresas = obter_empresas_usuario(user)
    empresa_id_ativa = getattr(user, "_empresa_ativa_id", None)
    if empresa_id_ativa:
        empresa_ativa = empresas.filter(pk=empresa_id_ativa).first()
        if empresa_ativa is not None:
            return empresa_ativa
    return empresas.first()


def obter_grupo_empresa_usuario(user):
    empresa = obter_empresa_ativa_usuario(user)
    return empresa.grupo if empresa else None


def obter_grupo_empresa_ou_erro(user):
    grupo = obter_grupo_empresa_usuario(user)
    if grupo is None:
        raise PermissionDenied("Usuário sem empresa vinculada.")
    return grupo


def queryset_da_empresa(queryset, user, field_name="empresa"):
    grupo = obter_grupo_empresa_usuario(user)
    if grupo is None:
        return queryset.none()
    return queryset.filter(**{field_name: grupo})


def pertence_a_empresa(obj, user, field_name="empresa_id"):
    grupo = obter_grupo_empresa_usuario(user)
    if grupo is None:
        return False
    return getattr(obj, field_name, None) == grupo.pk


def nome_grupo_visitante(username):
    return f"{VISITOR_GROUP_PREFIX}{username}"


def definir_empresa_ativa(request, user, empresa_id):
    if not getattr(user, "is_authenticated", False):
        return None

    try:
        empresa_id_int = int(empresa_id)
    except (TypeError, ValueError):
        return None

    empresa = obter_empresas_usuario(user).filter(pk=empresa_id_int).first()
    if empresa is None:
        return None

    request.session[EMPRESA_ATIVA_SESSION_KEY] = empresa.pk
    user._empresa_ativa_id = empresa.pk
    return empresa


def definir_grupo_empresa_ativo(request, user, grupo_id):
    try:
        grupo_id_int = int(grupo_id)
    except (TypeError, ValueError):
        return None
    empresa = obter_empresas_usuario(user).filter(grupo_id=grupo_id_int).first()
    if empresa is None:
        return None
    return definir_empresa_ativa(request, user, empresa.pk)
