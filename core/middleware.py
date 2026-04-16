from core.tenancy import EMPRESA_ATIVA_SESSION_KEY
from core.tenancy import obter_empresas_usuario


class EmpresaAtivaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            empresas = obter_empresas_usuario(user)
            empresa_id_ativa = request.session.get(EMPRESA_ATIVA_SESSION_KEY)

            if empresa_id_ativa is not None and not empresas.filter(pk=empresa_id_ativa).exists():
                request.session.pop(EMPRESA_ATIVA_SESSION_KEY, None)
                empresa_id_ativa = None

            if empresa_id_ativa is None:
                empresa_padrao = empresas.first()
                if empresa_padrao is not None:
                    empresa_id_ativa = empresa_padrao.pk
                    request.session[EMPRESA_ATIVA_SESSION_KEY] = empresa_id_ativa

            if empresa_id_ativa is not None:
                user._empresa_ativa_id = int(empresa_id_ativa)

        return self.get_response(request)
