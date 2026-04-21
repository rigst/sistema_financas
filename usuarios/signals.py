from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver

from .visitantes import limpar_dados_visitante


@receiver(user_logged_out)
def limpar_visitante_ao_sair(sender, request, user, **kwargs):
    limpar_dados_visitante(user)
