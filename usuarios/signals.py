from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.tenancy import obter_grupo_empresa_padrao
from .visitantes import limpar_dados_visitante


@receiver(post_save, sender=get_user_model())
def garantir_grupo_padrao_para_usuario(sender, instance, created, **kwargs):
    if not created or instance.eh_visitante or instance.groups.exists():
        return
    instance.groups.add(obter_grupo_empresa_padrao())


@receiver(user_logged_out)
def limpar_visitante_ao_sair(sender, request, user, **kwargs):
    limpar_dados_visitante(user)
