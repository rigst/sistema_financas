from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    # `= None` remove as M2M herdadas do AbstractUser. Os stubs declaram os
    # managers e não têm como expressar a remoção; `Any` é o que permite
    # sobrescrever sem espalhar `type: ignore`.
    groups: Any = None
    user_permissions: Any = None
    nome_exibicao = models.CharField(max_length=150, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome_exibicao or self.get_full_name() or self.username
