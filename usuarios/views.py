import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse

from legal.forms import AceiteForm
from legal.models import OrigemAceite
from legal.services import documentos_vigentes, registrar_aceite
from legal.utils import ip_do_request

from .models import Usuario
from .visitantes import (
    excedeu_rate_limit_visitante,
    limpar_visitantes_expirados,
    registrar_tentativa_visitante,
)

logger = logging.getLogger(__name__)


class UsuarioLoginView(LoginView):
    template_name = "registration/login.html"
    # Sem isto, visitar /login/ já autenticado renderiza o formulário de novo
    # em vez de mandar para o painel — o casco de página pública que a tela
    # usa nem existe para quem está logado, e o resultado sai quebrado.
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if "entrar_visitante" in request.POST:
            return self.entrar_como_visitante(request)
        return super().post(request, *args, **kwargs)

    def entrar_como_visitante(self, request):
        # O aceite é condição para criar a conta: valida antes de qualquer
        # escrita, para não deixar visitante órfão sem prova de aceite.
        form_aceite = AceiteForm(request.POST)
        if not form_aceite.is_valid():
            # Volta para a própria tela de aceite com o erro: o checkbox não
            # existe mais no login, então renderizá-lo lá esconderia a mensagem.
            return render(
                request,
                "legal/aceite.html",
                {
                    "form": form_aceite,
                    "documentos": list(documentos_vigentes().values()),
                    "action": reverse("login"),
                    "campos_extras": settings.LEGAL_VISITOR_EXTRA,
                },
            )

        ip = ip_do_request(request)
        if excedeu_rate_limit_visitante(ip):
            logger.warning("Rate limit de visitante excedido", extra={"ip": ip})
            messages.error(
                request,
                "Muitas tentativas de acesso visitante em pouco tempo. Aguarde alguns minutos e tente novamente.",
            )
            return redirect(reverse("login"))
        registrar_tentativa_visitante(ip)
        return self.criar_e_logar_visitante()

    def criar_e_logar_visitante(self):
        limpar_visitantes_expirados()
        token = secrets.token_hex(4)
        username = f"visitante_{token}"
        usuario = Usuario.objects.create_user(
            username=username,
            password=secrets.token_urlsafe(24),
            nome_exibicao="Visitante",
        )
        login(self.request, usuario)
        registrar_aceite(
            self.request,
            usuario=usuario,
            origem=OrigemAceite.VISITANTE,
            e_visitante=True,
        )
        return redirect(reverse("dashboard"))


class UsuarioLogoutView(LogoutView):
    pass
