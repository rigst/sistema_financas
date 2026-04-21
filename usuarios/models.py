from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    groups = None
    user_permissions = None
    nome_exibicao = models.CharField(max_length=150, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome_exibicao or self.get_full_name() or self.username
