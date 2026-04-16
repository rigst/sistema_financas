from django.db import models

from core.tenancy import obter_grupo_empresa_padrao


class Cliente(models.Model):
    TIPO_PESSOA_CHOICES = [
        ("PF", "Pessoa Física"),
        ("PJ", "Pessoa Jurídica"),
    ]

    tipo_pessoa = models.CharField(
        max_length=2,
        choices=TIPO_PESSOA_CHOICES,
        default="PF",
    )
    nome_razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)

    cpf_cnpj = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    contato_responsavel = models.CharField(max_length=255, blank=True)

    cep = models.CharField(max_length=10, blank=True)
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=255, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)

    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="clientes",
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome_razao_social"]

    def __str__(self):
        return self.nome_razao_social

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = obter_grupo_empresa_padrao()
        super().save(*args, **kwargs)
