import secrets
import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse

from core.tenancy import nome_grupo_visitante
from .models import Usuario
from .visitantes import (
    excedeu_rate_limit_visitante,
    limpar_visitantes_expirados,
    registrar_tentativa_visitante,
)

logger = logging.getLogger(__name__)


class UsuarioLoginView(LoginView):
    template_name = "registration/login.html"

    def _client_ip(self):
        forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            # Behind nginx with `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`,
            # the right-most entry is the direct client IP observed by nginx.
            return forwarded_for.split(",")[-1].strip()
        return self.request.META.get("REMOTE_ADDR", "")

    def post(self, request, *args, **kwargs):
        if "entrar_visitante" in request.POST:
            ip = self._client_ip()
            if excedeu_rate_limit_visitante(ip):
                logger.warning("Rate limit de visitante excedido", extra={"ip": ip})
                messages.error(
                    request,
                    "Muitas tentativas de acesso visitante em pouco tempo. Aguarde alguns minutos e tente novamente.",
                )
                return redirect(reverse("login"))
            registrar_tentativa_visitante(ip)
            return self.criar_e_logar_visitante()
        return super().post(request, *args, **kwargs)

    def criar_e_logar_visitante(self):
        limpar_visitantes_expirados()
        token = secrets.token_hex(4)
        username = f"visitante_{token}"
        grupo = Group.objects.create(name=nome_grupo_visitante(username))
        usuario = Usuario.objects.create_user(
            username=username,
            password=secrets.token_urlsafe(24),
            perfil="visitante",
            nome_exibicao="Visitante",
        )
        usuario.groups.add(grupo)
        login(self.request, usuario)
        return redirect(reverse("dashboard"))


class UsuarioLogoutView(LogoutView):
    pass
