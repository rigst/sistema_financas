from django.db import models


class Empresa(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    grupo = models.OneToOneField(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="empresa_registro",
    )
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome
