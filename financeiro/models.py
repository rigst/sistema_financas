from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.tenancy import obter_grupo_empresa_padrao

DUAS_CASAS = Decimal("0.01")


def arredondar(valor: Decimal) -> Decimal:
    return Decimal(valor or 0).quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)


class Conta(models.Model):
    TIPO_CHOICES = [
        ("corrente", "Conta corrente"),
        ("poupanca", "Poupança"),
        ("dinheiro", "Dinheiro"),
        ("investimento", "Investimento"),
        ("beneficio", "Benefício"),
        ("outro", "Outro"),
    ]

    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="corrente")
    instituicao = models.CharField(max_length=120, blank=True)
    saldo_inicial = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    data_saldo_inicial = models.DateField(null=True, blank=True)
    cor = models.CharField(max_length=7, default="#2563EB")
    ativa = models.BooleanField(default=True)
    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="contas_financeiras",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "nome"], name="conta_empresa_nome_uniq"),
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = obter_grupo_empresa_padrao()
        super().save(*args, **kwargs)

    def saldo_atual(self):
        total = self.saldo_inicial
        transacoes = self.transacoes.filter(status="pago")
        for transacao in transacoes:
            total += transacao.impacto_na_conta(self)
        transferencias_recebidas = self.transferencias_recebidas.filter(status="pago")
        for transacao in transferencias_recebidas:
            total += transacao.impacto_na_conta(self)
        return arredondar(total)


class CategoriaFinanceira(models.Model):
    TIPO_CHOICES = [
        ("receita", "Receita"),
        ("despesa", "Despesa"),
    ]
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

    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    categoria_pai = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="subcategorias",
        null=True,
        blank=True,
    )
    cor = models.CharField(max_length=7, choices=COLOR_CHOICES, default="#2563EB")
    icone = models.CharField(max_length=40, blank=True)
    ativa = models.BooleanField(default=True)
    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="categorias_financeiras",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tipo", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "tipo", "nome"], name="categoriafinanceira_empresa_tipo_nome_uniq"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    def clean(self):
        if self.categoria_pai_id:
            if self.categoria_pai_id == self.pk:
                raise ValidationError({"categoria_pai": "A categoria não pode ser pai dela mesma."})
            if self.categoria_pai.tipo != self.tipo:
                raise ValidationError({"categoria_pai": "A categoria pai deve ter o mesmo tipo."})
            if self.empresa_id and self.categoria_pai.empresa_id != self.empresa_id:
                raise ValidationError({"categoria_pai": "Selecione uma categoria pai do mesmo espaço financeiro."})

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = obter_grupo_empresa_padrao()
        super().save(*args, **kwargs)


class Transacao(models.Model):
    TIPO_CHOICES = [
        ("receita", "Receita"),
        ("despesa", "Despesa"),
        ("transferencia", "Transferência"),
    ]
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("pago", "Pago"),
        ("cancelado", "Cancelado"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    data_competencia = models.DateField()
    data_pagamento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    conta = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="transacoes",
    )
    conta_destino = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="transferencias_recebidas",
        null=True,
        blank=True,
    )
    categoria = models.ForeignKey(
        CategoriaFinanceira,
        on_delete=models.PROTECT,
        related_name="transacoes",
        null=True,
        blank=True,
    )
    observacoes = models.TextField(blank=True)
    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="transacoes_financeiras",
        null=True,
        blank=True,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transacoes_financeiras_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_competencia", "-id"]

    def __str__(self):
        return f"{self.descricao} - {arredondar(self.valor)}"

    def clean(self):
        if self.tipo == "transferencia":
            if not self.conta_destino_id:
                raise ValidationError({"conta_destino": "Informe a conta destino da transferência."})
            if self.conta_id and self.conta_destino_id == self.conta_id:
                raise ValidationError({"conta_destino": "A conta destino deve ser diferente da conta origem."})
            if self.categoria_id:
                raise ValidationError({"categoria": "Transferências não usam categoria."})
        else:
            if self.conta_destino_id:
                raise ValidationError({"conta_destino": "Conta destino só deve ser usada em transferências."})
            if not self.categoria_id:
                raise ValidationError({"categoria": "Informe a categoria."})
            if self.categoria.tipo != self.tipo:
                raise ValidationError({"categoria": "A categoria deve ter o mesmo tipo da transação."})

        empresa_id = self.empresa_id or getattr(self.conta, "empresa_id", None)
        if empresa_id:
            if self.conta_id and self.conta.empresa_id != empresa_id:
                raise ValidationError({"conta": "Selecione uma conta do mesmo espaço financeiro."})
            if self.conta_destino_id and self.conta_destino.empresa_id != empresa_id:
                raise ValidationError({"conta_destino": "Selecione uma conta destino do mesmo espaço financeiro."})
            if self.categoria_id and self.categoria.empresa_id != empresa_id:
                raise ValidationError({"categoria": "Selecione uma categoria do mesmo espaço financeiro."})

        if self.status == "pago" and not self.data_pagamento:
            raise ValidationError({"data_pagamento": "Informe a data de pagamento/recebimento."})

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = self.conta.empresa if self.conta_id else obter_grupo_empresa_padrao()
        self.full_clean()
        super().save(*args, **kwargs)

    def impacto_na_conta(self, conta):
        valor = arredondar(self.valor)
        if self.status != "pago":
            return Decimal("0.00")
        if self.tipo == "receita" and self.conta_id == conta.pk:
            return valor
        if self.tipo == "despesa" and self.conta_id == conta.pk:
            return -valor
        if self.tipo == "transferencia":
            if self.conta_id == conta.pk:
                return -valor
            if self.conta_destino_id == conta.pk:
                return valor
        return Decimal("0.00")


class CartaoCredito(models.Model):
    BANDEIRA_CHOICES = [
        ("visa", "Visa"),
        ("mastercard", "Mastercard"),
        ("elo", "Elo"),
        ("amex", "American Express"),
        ("hipercard", "Hipercard"),
        ("outra", "Outra"),
    ]

    nome = models.CharField(max_length=120)
    bandeira = models.CharField(max_length=20, choices=BANDEIRA_CHOICES, default="outra")
    limite = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])
    dia_fechamento = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)])
    dia_vencimento = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)])
    conta_pagamento = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="cartoes", null=True, blank=True)
    cor = models.CharField(max_length=7, default="#111827")
    ativo = models.BooleanField(default=True)
    empresa = models.ForeignKey("auth.Group", on_delete=models.PROTECT, related_name="cartoes_credito", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["empresa", "nome"], name="cartaocredito_empresa_nome_uniq")]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = obter_grupo_empresa_padrao()
        super().save(*args, **kwargs)


class OrcamentoMensal(models.Model):
    mes = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    ano = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="orcamentos_mensais")
    valor_planejado = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    empresa = models.ForeignKey("auth.Group", on_delete=models.PROTECT, related_name="orcamentos_mensais", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-mes", "categoria__nome"]
        constraints = [models.UniqueConstraint(fields=["empresa", "ano", "mes", "categoria"], name="orcamentomensal_empresa_periodo_categoria_uniq")]

    def __str__(self):
        return f"{self.categoria} - {self.mes:02d}/{self.ano}"

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = self.categoria.empresa if self.categoria_id else obter_grupo_empresa_padrao()
        super().save(*args, **kwargs)


class MetaFinanceira(models.Model):
    STATUS_CHOICES = [
        ("ativa", "Ativa"),
        ("concluida", "Concluída"),
        ("pausada", "Pausada"),
        ("cancelada", "Cancelada"),
    ]

    nome = models.CharField(max_length=160)
    valor_alvo = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    valor_atual_manual = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])
    data_inicio = models.DateField(null=True, blank=True)
    data_limite = models.DateField(null=True, blank=True)
    conta_vinculada = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="metas", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativa")
    cor = models.CharField(max_length=7, default="#16A34A")
    observacoes = models.TextField(blank=True)
    empresa = models.ForeignKey("auth.Group", on_delete=models.PROTECT, related_name="metas_financeiras", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def valor_atual(self):
        if self.conta_vinculada_id:
            return self.conta_vinculada.saldo_atual()
        return arredondar(self.valor_atual_manual)

    @property
    def percentual_concluido(self):
        if not self.valor_alvo:
            return Decimal("0.00")
        percentual = (self.valor_atual / self.valor_alvo) * Decimal("100")
        return min(arredondar(percentual), Decimal("100.00"))

    def save(self, *args, **kwargs):
        if self.empresa_id is None:
            self.empresa = self.conta_vinculada.empresa if self.conta_vinculada_id else obter_grupo_empresa_padrao()
        super().save(*args, **kwargs)
