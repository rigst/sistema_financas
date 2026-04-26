import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Case, DecimalField, Q, Sum, Value, When
from django.db.models.functions import Coalesce

DUAS_CASAS = Decimal("0.01")


def arredondar(valor: Decimal) -> Decimal:
    return Decimal(valor or 0).quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)


def adicionar_meses_data(data_base, incremento):
    total = (data_base.year * 12) + (data_base.month - 1) + incremento
    mes = (total % 12) + 1
    ano = total // 12
    dia = min(data_base.day, calendar.monthrange(ano, mes)[1])
    return data_base.replace(year=ano, month=mes, day=dia)


def normalizar_competencia(valor):
    if not valor:
        return valor
    return valor.replace(day=1)


class Receita(models.Model):
    TIPO_CHOICES = [
        ("variavel", "Variável"),
        ("fixa", "Fixa"),
        ("parcelada", "Parcelada"),
    ]
    STATUS_CHOICES = [
        ("recebida", "Recebida"),
        ("prevista", "Prevista"),
    ]

    descricao = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="variavel")
    valor = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    data = models.DateField(default=date.today)
    competencia = models.DateField()
    categoria = models.CharField(max_length=120, blank=True)
    parcelas = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(120)])
    parcela_atual = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(120)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="recebida")
    data_recebimento = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    ativa = models.BooleanField(default=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="receitas_criadas")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["criado_por", "data"], name="receita_user_data_idx"),
            models.Index(fields=["criado_por", "status"], name="receita_user_status_idx"),
        ]

    def __str__(self):
        return self.descricao

    def clean(self):
        if self.tipo != "parcelada" and self.parcelas != 1:
            raise ValidationError({"parcelas": "Use parcelas apenas para receita parcelada."})
        if self.tipo != "parcelada" and self.parcela_atual != 1:
            raise ValidationError({"parcela_atual": "Use parcela atual apenas para receita parcelada."})
        if self.tipo == "parcelada" and self.parcelas < 2:
            raise ValidationError({"parcelas": "Receita parcelada precisa ter pelo menos 2 parcelas."})
        if self.tipo == "parcelada" and self.parcela_atual > self.parcelas:
            raise ValidationError({"parcela_atual": "A parcela atual não pode ser maior que o total de parcelas."})
        if not self.competencia:
            self.competencia = self.data
        self.competencia = normalizar_competencia(self.competencia)
        if self.status == "recebida" and not self.data_recebimento:
            self.data_recebimento = self.data
        if self.status == "prevista":
            self.data_recebimento = None

    def save(self, *args, **kwargs):
        if not self.competencia:
            self.competencia = self.data
        self.competencia = normalizar_competencia(self.competencia)
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def valor_parcela(self):
        if self.tipo != "parcelada":
            return arredondar(self.valor)
        return arredondar(self.valor / Decimal(self.parcelas))

    def ocorrencias(self, inicio, fim):
        data_recebimento = self.data_recebimento or self.data
        if self.tipo == "fixa":
            ocorrencias = []
            indice = 0
            while indice < 120:
                competencia_ocorrencia = adicionar_meses_data(self.competencia, indice)
                if competencia_ocorrencia > fim:
                    break
                if competencia_ocorrencia >= inicio:
                    data_ocorrencia = adicionar_meses_data(self.data, indice)
                    recebida = self.status == "recebida" and data_ocorrencia <= data_recebimento
                    ocorrencias.append(
                        {
                            "data": data_ocorrencia,
                            "competencia": competencia_ocorrencia,
                            "valor": arredondar(self.valor),
                            "parcela": None,
                            "status": "recebida" if recebida else "prevista",
                            "data_recebimento": data_recebimento if recebida else None,
                        }
                    )
                indice += 1
            return ocorrencias
        if self.tipo == "parcelada":
            ocorrencias = []
            inicio_indice = self.parcela_atual - 1
            for indice in range(inicio_indice, self.parcelas):
                incremento = indice - inicio_indice
                competencia_ocorrencia = adicionar_meses_data(self.competencia, incremento)
                if not inicio <= competencia_ocorrencia <= fim:
                    continue
                data_ocorrencia = adicionar_meses_data(self.data, incremento)
                recebida = self.status == "recebida" and data_ocorrencia <= data_recebimento
                ocorrencias.append(
                    {
                        "data": data_ocorrencia,
                        "competencia": competencia_ocorrencia,
                        "valor": self.valor_parcela,
                        "parcela": indice + 1,
                        "status": "recebida" if recebida else "prevista",
                        "data_recebimento": data_recebimento if recebida else None,
                    }
                )
            return ocorrencias
        if inicio <= self.competencia <= fim:
            return [
                {
                    "data": self.data,
                    "competencia": self.competencia,
                    "valor": arredondar(self.valor),
                    "parcela": None,
                    "status": self.status,
                    "data_recebimento": self.data_recebimento,
                }
            ]
        return []

    def parcela_na_data(self, referencia=None):
        referencia = referencia or date.today()
        if self.tipo != "parcelada":
            return None
        meses_decorridos = (referencia.year - self.competencia.year) * 12 + (referencia.month - self.competencia.month)
        if meses_decorridos < 0:
            return self.parcela_atual
        return min(self.parcela_atual + meses_decorridos, self.parcelas)


class Despesa(models.Model):
    TIPO_CHOICES = [
        ("variavel", "Variável"),
        ("fixa", "Fixa"),
        ("parcelada", "Parcelada"),
    ]
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("paga", "Paga"),
        ("cancelada", "Cancelada"),
    ]

    descricao = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="variavel")
    valor = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    data = models.DateField(default=date.today)
    competencia = models.DateField()
    categoria = models.CharField(max_length=120, blank=True)
    parcelas = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(120)])
    parcela_atual = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(120)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    observacoes = models.TextField(blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="despesas_criadas")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["criado_por", "data"], name="despesa_user_data_idx"),
            models.Index(fields=["criado_por", "status", "tipo"], name="despesa_user_stat_tipo_idx"),
        ]

    def __str__(self):
        return self.descricao

    def clean(self):
        if self.tipo != "parcelada" and self.parcelas != 1:
            raise ValidationError({"parcelas": "Use parcelas apenas para despesa parcelada."})
        if self.tipo != "parcelada" and self.parcela_atual != 1:
            raise ValidationError({"parcela_atual": "Use parcela atual apenas para despesa parcelada."})
        if self.tipo == "parcelada" and self.parcelas < 2:
            raise ValidationError({"parcelas": "Despesa parcelada precisa ter pelo menos 2 parcelas."})
        if self.tipo == "parcelada" and self.parcela_atual > self.parcelas:
            raise ValidationError({"parcela_atual": "A parcela atual não pode ser maior que o total de parcelas."})
        if not self.competencia:
            self.competencia = self.data
        self.competencia = normalizar_competencia(self.competencia)

    def save(self, *args, **kwargs):
        if not self.competencia:
            self.competencia = self.data
        self.competencia = normalizar_competencia(self.competencia)
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def valor_parcela(self):
        if self.tipo != "parcelada":
            return arredondar(self.valor)
        return arredondar(self.valor / Decimal(self.parcelas))

    def ocorrencias(self, inicio, fim):
        if self.status == "cancelada":
            return []
        if self.tipo == "fixa":
            ocorrencias = []
            indice = 0
            while indice < 120:
                competencia_ocorrencia = adicionar_meses_data(self.competencia, indice)
                if competencia_ocorrencia > fim:
                    break
                if competencia_ocorrencia >= inicio:
                    ocorrencias.append(
                        {
                            "data": adicionar_meses_data(self.data, indice),
                            "competencia": competencia_ocorrencia,
                            "valor": arredondar(self.valor),
                            "parcela": None,
                            "status": self.status,
                        }
                    )
                indice += 1
            return ocorrencias
        if self.tipo == "parcelada":
            inicio_indice = self.parcela_atual - 1
            return [
                {
                    "data": adicionar_meses_data(self.data, indice - inicio_indice),
                    "competencia": adicionar_meses_data(self.competencia, indice - inicio_indice),
                    "valor": self.valor_parcela,
                    "parcela": indice + 1,
                    "status": self.status,
                }
                for indice in range(inicio_indice, self.parcelas)
                if inicio <= adicionar_meses_data(self.competencia, indice - inicio_indice) <= fim
            ]
        if inicio <= self.competencia <= fim:
            return [
                {
                    "data": self.data,
                    "competencia": self.competencia,
                    "valor": arredondar(self.valor),
                    "parcela": None,
                    "status": self.status,
                }
            ]
        return []

    def parcela_na_data(self, referencia=None):
        referencia = referencia or date.today()
        if self.tipo != "parcelada":
            return None
        meses_decorridos = (referencia.year - self.competencia.year) * 12 + (referencia.month - self.competencia.month)
        if meses_decorridos < 0:
            return self.parcela_atual
        return min(self.parcela_atual + meses_decorridos, self.parcelas)


class Reserva(models.Model):
    nome = models.CharField(max_length=160)
    valor_atual = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])
    valor_alvo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])
    observacoes = models.TextField(blank=True)
    ativa = models.BooleanField(default=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservas_criadas", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def percentual_concluido(self):
        if not self.valor_alvo:
            return Decimal("0.00")
        return min(arredondar((self.valor_atual / self.valor_alvo) * Decimal("100")), Decimal("100.00"))


class MentoriaFinanceiraIA(models.Model):
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mentorias_financeiras_ia")
    periodo_inicio = models.DateField()
    periodo_fim = models.DateField()
    conteudo = models.TextField()
    dados_enviados = models.JSONField(default=dict, blank=True)
    modelo = models.CharField(max_length=80, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["criado_por", "-criado_em"], name="mentoria_user_criado_idx"),
        ]

    def __str__(self):
        return f"Mentoria IA de {self.periodo_inicio:%d/%m/%Y} a {self.periodo_fim:%d/%m/%Y}"

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
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["nome"], name="conta_nome_uniq"),
        ]

    def __str__(self):
        return self.nome

    def saldo_atual(self):
        saldo_movimentacoes = Transacao.objects.filter(
            Q(conta=self) | Q(conta_destino=self),
            status="pago",
        ).aggregate(
            total=Coalesce(
                Sum(
                    Case(
                        When(tipo="receita", conta=self, then="valor"),
                        When(tipo="despesa", conta=self, then=-models.F("valor")),
                        When(tipo="transferencia", conta=self, then=-models.F("valor")),
                        When(tipo="transferencia", conta_destino=self, then="valor"),
                        default=Value(Decimal("0.00")),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )
                ),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )["total"]
        return arredondar(self.saldo_inicial + saldo_movimentacoes)


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
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tipo", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "nome"], name="categoriafinanceira_tipo_nome_uniq"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    def clean(self):
        if self.categoria_pai_id:
            if self.categoria_pai_id == self.pk:
                raise ValidationError({"categoria_pai": "A categoria não pode ser pai dela mesma."})
            if self.categoria_pai.tipo != self.tipo:
                raise ValidationError({"categoria_pai": "A categoria pai deve ter o mesmo tipo."})


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
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transacoes_financeiras_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_competencia", "-id"]
        indexes = [
            models.Index(fields=["criado_por", "data_competencia"], name="trans_user_data_idx"),
            models.Index(fields=["criado_por", "status", "tipo"], name="trans_user_stat_tipo_idx"),
            models.Index(fields=["conta", "status"], name="trans_conta_stat_idx"),
            models.Index(fields=["conta_destino", "status"], name="trans_dest_stat_idx"),
        ]

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

        if self.status == "pago" and not self.data_pagamento:
            raise ValidationError({"data_pagamento": "Informe a data de pagamento/recebimento."})

    def save(self, *args, **kwargs):
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
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["nome"], name="cartaocredito_nome_uniq")]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class FaturaCartao(models.Model):
    STATUS_CHOICES = [
        ("aberta", "Aberta"),
        ("fechada", "Fechada"),
        ("paga", "Paga"),
        ("cancelada", "Cancelada"),
    ]

    cartao = models.ForeignKey(CartaoCredito, on_delete=models.PROTECT, related_name="faturas")
    mes = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    ano = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    data_fechamento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="aberta")
    conta_pagamento = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="faturas_cartao", null=True, blank=True)
    categoria_pagamento = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="faturas_cartao", null=True, blank=True)
    transacao_pagamento = models.ForeignKey(Transacao, on_delete=models.PROTECT, related_name="faturas_cartao_pagas", null=True, blank=True)
    data_pagamento = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-mes", "cartao__nome"]
        indexes = [
            models.Index(fields=["status"], name="fatura_status_idx"),
            models.Index(fields=["ano", "mes"], name="fatura_periodo_idx"),
        ]
        constraints = [models.UniqueConstraint(fields=["cartao", "ano", "mes"], name="faturacartao_cartao_periodo_uniq")]

    def __str__(self):
        return f"{self.cartao} - {self.mes:02d}/{self.ano}"

    @property
    def valor_total(self):
        total = self.lancamentos.exclude(status="cancelado").aggregate(
            total=Coalesce(Sum("valor"), Decimal("0.00"), output_field=models.DecimalField(max_digits=14, decimal_places=2))
        )["total"]
        return arredondar(total)

    def clean(self):
        if self.categoria_pagamento_id and self.categoria_pagamento.tipo != "despesa":
            raise ValidationError({"categoria_pagamento": "A categoria de pagamento deve ser de despesa."})
        if self.status == "paga":
            if not self.conta_pagamento_id:
                raise ValidationError({"conta_pagamento": "Informe a conta de pagamento."})
            if not self.categoria_pagamento_id:
                raise ValidationError({"categoria_pagamento": "Informe a categoria de pagamento."})
            if not self.data_pagamento:
                raise ValidationError({"data_pagamento": "Informe a data de pagamento."})
            if not self.transacao_pagamento_id:
                raise ValidationError({"status": "Use a ação Pagar fatura para criar a baixa bancária."})

    def save(self, *args, **kwargs):
        if self.conta_pagamento_id is None and self.cartao_id and self.cartao.conta_pagamento_id:
            self.conta_pagamento = self.cartao.conta_pagamento
        self.full_clean()
        super().save(*args, **kwargs)

    def pagar(self, *, conta, categoria, data_pagamento, usuario):
        if self.status == "paga":
            return self.transacao_pagamento
        if self.status == "cancelada":
            raise ValidationError("Faturas canceladas não podem ser pagas.")
        if self.valor_total <= Decimal("0.00"):
            raise ValidationError("Faturas sem valor não podem ser pagas.")
        transacao = Transacao.objects.create(
            tipo="despesa",
            descricao=f"Pagamento fatura {self.cartao.nome} {self.mes:02d}/{self.ano}",
            valor=self.valor_total,
            data_competencia=data_pagamento,
            data_pagamento=data_pagamento,
            status="pago",
            conta=conta,
            categoria=categoria,
            criado_por=usuario,
        )
        self.status = "paga"
        self.conta_pagamento = conta
        self.categoria_pagamento = categoria
        self.data_pagamento = data_pagamento
        self.transacao_pagamento = transacao
        self.save(update_fields=["status", "conta_pagamento", "categoria_pagamento", "data_pagamento", "transacao_pagamento", "atualizado_em"])
        return transacao


class LancamentoCartao(models.Model):
    STATUS_CHOICES = [
        ("ativo", "Ativo"),
        ("cancelado", "Cancelado"),
    ]

    fatura = models.ForeignKey(FaturaCartao, on_delete=models.CASCADE, related_name="lancamentos")
    cartao = models.ForeignKey(CartaoCredito, on_delete=models.PROTECT, related_name="lancamentos")
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="lancamentos_cartao")
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    data_compra = models.DateField(default=date.today)
    parcela_numero = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    parcela_total = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativo")
    observacoes = models.TextField(blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lancamentos_cartao_criados")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_compra", "-id"]
        indexes = [
            models.Index(fields=["criado_por", "data_compra"], name="lanc_card_user_data_idx"),
            models.Index(fields=["fatura", "status"], name="lanc_card_fat_stat_idx"),
        ]

    def __str__(self):
        if self.parcela_total > 1:
            return f"{self.descricao} ({self.parcela_numero}/{self.parcela_total})"
        return self.descricao

    def clean(self):
        if self.parcela_numero > self.parcela_total:
            raise ValidationError({"parcela_numero": "A parcela atual não pode ser maior que o total de parcelas."})
        if self.categoria_id and self.categoria.tipo != "despesa":
            raise ValidationError({"categoria": "Lançamentos de cartão exigem categoria de despesa."})
        if self.fatura_id and self.cartao_id and self.fatura.cartao_id != self.cartao_id:
            raise ValidationError({"fatura": "A fatura deve pertencer ao cartão selecionado."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RecorrenciaFinanceira(models.Model):
    TIPO_CHOICES = Transacao.TIPO_CHOICES[:2]
    FREQUENCIA_CHOICES = [
        ("mensal", "Mensal"),
        ("semanal", "Semanal"),
        ("quinzenal", "Quinzenal"),
        ("anual", "Anual"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="recorrencias")
    conta = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="recorrencias")
    frequencia = models.CharField(max_length=20, choices=FREQUENCIA_CHOICES, default="mensal")
    dia_vencimento = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)], default=1)
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorrencias_financeiras_criadas")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["descricao"]

    def __str__(self):
        return self.descricao

    def clean(self):
        if self.categoria_id and self.categoria.tipo != self.tipo:
            raise ValidationError({"categoria": "A categoria deve ter o mesmo tipo da recorrência."})
        if self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "A data final não pode ser anterior à data inicial."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PlanejamentoMensal(models.Model):
    mes = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    ano = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="planejamentos_mensais")
    valor_planejado = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-mes", "categoria__nome"]
        constraints = [models.UniqueConstraint(fields=["ano", "mes", "categoria"], name="planejamentomensal_periodo_categoria_uniq")]

    def __str__(self):
        return f"{self.categoria} - {self.mes:02d}/{self.ano}"

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
