from django.db import models

from core.tenancy import obter_grupo_empresa_padrao


class ConfiguracaoEmpresa(models.Model):
    nome_empresa = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)

    cpf_cnpj = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    site = models.URLField(blank=True)

    cep = models.CharField(max_length=10, blank=True)
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=255, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)

    dados_bancarios = models.TextField(blank=True)
    chave_pix = models.CharField(max_length=255, blank=True)
    validade_padrao_proposta = models.CharField(max_length=100, blank=True)
    assinatura_nome = models.CharField(max_length=255, blank=True)
    assinatura_cargo = models.CharField(max_length=255, blank=True)
    assinatura_contato = models.CharField(max_length=255, blank=True)
    texto_institucional_memorial = models.TextField(blank=True)

    rodape_relatorio = models.TextField(blank=True)
    logo = models.ImageField(upload_to="empresa/logos/", blank=True, null=True)
    ativo = models.BooleanField(default=True)
    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="configuracoes_empresa",
        null=True,
        blank=True,
    )

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração da empresa"
        verbose_name_plural = "Configurações da empresa"

    def __str__(self):
        return self.nome_empresa

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = obter_grupo_empresa_padrao()
        super().save(*args, **kwargs)
