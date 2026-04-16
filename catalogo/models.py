from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import IntegrityError, models
from django.db.models import Max

from core.tenancy import obter_grupo_empresa_padrao


class CategoriaItem(models.Model):
    COLOR_CHOICES = [
        ("#2563EB", "Azul"),
        ("#DC2626", "Vermelho"),
        ("#EAB308", "Amarelo"),
        ("#16A34A", "Verde"),
        ("#EA580C", "Laranja"),
        ("#7C3AED", "Roxo"),
        ("#DB2777", "Rosa"),
        ("#92400E", "Marrom"),
        ("#111827", "Preto"),
        ("#475569", "Grafite"),
    ]

    COLOR_SEQUENCE = [
        "#2563EB",
        "#DC2626",
        "#EAB308",
        "#16A34A",
        "#EA580C",
        "#7C3AED",
        "#DB2777",
        "#92400E",
        "#111827",
        "#475569",
    ]

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    cor = models.CharField(max_length=7, choices=COLOR_CHOICES, default="#2563EB")
    ativo = models.BooleanField(default=True)
    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="categorias_catalogo",
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Categoria de item"
        verbose_name_plural = "Categorias de itens"
        constraints = [
            models.UniqueConstraint(fields=["empresa", "nome"], name="categoriaitem_empresa_nome_uniq"),
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = obter_grupo_empresa_padrao()
        super().save(*args, **kwargs)


class ItemCatalogo(models.Model):
    UNIDADE_CHOICES = [
        ("un", "Unidade"),
        ("hr", "Hora"),
        ("dia", "Diária"),
        ("m", "m"),
        ("m2", "m2"),
        ("m3", "m3"),
        ("kg", "Quilo"),
        ("cx", "Caixa"),
        ("pct", "Pacote"),
        ("sv", "Serviço"),
        ("-", "-"),
    ]

    codigo = models.CharField(max_length=50)
    nome = models.CharField(max_length=255)
    descricao_padrao = models.TextField(blank=True)

    categoria = models.ForeignKey(
        CategoriaItem,
        on_delete=models.PROTECT,
        related_name="itens",
        null=True,
        blank=True,
    )

    unidade_medida = models.CharField(
        max_length=10,
        choices=UNIDADE_CHOICES,
        default="un",
    )

    valor_unitario_padrao = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="itens_catalogo",
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Item de catálogo"
        verbose_name_plural = "Itens de catálogo"
        constraints = [
            models.UniqueConstraint(fields=["empresa", "codigo"], name="itemcatalogo_empresa_codigo_uniq"),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    @classmethod
    def gerar_proximo_codigo(cls) -> str:
        prefixo = "CAT-ITEM-"
        queryset = cls.objects.filter(codigo__startswith=prefixo)
        if getattr(cls, "_empresa_codigo_context", None) is not None:
            queryset = queryset.filter(empresa=cls._empresa_codigo_context)
        ultimo_codigo = queryset.aggregate(max_codigo=Max("codigo"))["max_codigo"]
        sequencial = 1
        if ultimo_codigo:
            try:
                sequencial = int(str(ultimo_codigo).rsplit("-", 1)[-1]) + 1
            except (TypeError, ValueError):
                sequencial = 1
        return f"{prefixo}{sequencial:04d}"

    def definir_codigo_automatico(self):
        if self.pk:
            codigo_original = type(self).objects.filter(pk=self.pk).values_list("codigo", flat=True).first()
            if codigo_original:
                self.codigo = codigo_original
                return
        self.codigo = self.gerar_proximo_codigo()

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = obter_grupo_empresa_padrao()
        max_tentativas = 5 if not self.pk else 1
        for tentativa in range(max_tentativas):
            type(self)._empresa_codigo_context = self.empresa
            try:
                self.definir_codigo_automatico()
                self.full_clean()
                super().save(*args, **kwargs)
                return
            except IntegrityError as exc:
                if self.pk or tentativa == max_tentativas - 1:
                    raise
                if "itemcatalogo_empresa_codigo_uniq" not in str(exc) and "UNIQUE constraint failed" not in str(exc):
                    raise
            finally:
                type(self)._empresa_codigo_context = None
