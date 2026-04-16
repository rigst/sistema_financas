from core.tenancy import obter_empresa_ativa_usuario, obter_empresas_usuario


def empresa_context(request):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {}

    empresas_usuario = list(obter_empresas_usuario(user))
    empresa_ativa = obter_empresa_ativa_usuario(user)
    return {
        "empresas_usuario": empresas_usuario,
        "empresa_ativa": empresa_ativa,
    }
