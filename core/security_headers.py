from django.conf import settings
import secrets


class ContentSecurityPolicyMiddleware:
    """Aplica a CSP, com uma política própria (e mais frouxa) para o /admin/.

    O app público mantém a política estrita: script só do próprio domínio ou com
    nonce. O admin não cabe nela porque o tema (django-unfold) usa Alpine.js, que
    avalia as expressões dos atributos `x-data`/`x-init` via `new Function()` e
    portanto exige 'unsafe-eval'. Em vez de afrouxar o site inteiro por causa do
    painel, a exceção fica restrita ao prefixo do admin — que já é acessível
    apenas a quem tem `is_staff`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _politica(self, request):
        prefixo = getattr(settings, "ADMIN_PATH_PREFIX", "/admin/")
        if request.path.startswith(prefixo):
            return (
                getattr(settings, "CONTENT_SECURITY_POLICY_ADMIN", "")
                or settings.CONTENT_SECURITY_POLICY
            )
        return settings.CONTENT_SECURITY_POLICY

    def __call__(self, request):
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce
        response = self.get_response(request)
        if getattr(settings, "ENABLE_CSP", False) and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self._politica(request).format(nonce=nonce)
        return response
