from decimal import Decimal, ROUND_HALF_UP

from django import forms

from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import substituir_por_decimal_br
from core.tenancy import queryset_da_empresa
from .models import CategoriaFinanceira, Conta, CartaoCredito, FaturaCartao, MetaFinanceira, PlanejamentoMensal, RecorrenciaFinanceira, Transacao


class ContaForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = Conta
        fields = [
            "nome",
            "tipo",
            "instituicao",
            "saldo_inicial",
            "data_saldo_inicial",
            "cor",
            "ativa",
        ]
        widgets = {"data_saldo_inicial": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativa"].widget = forms.HiddenInput()
        self.fields["ativa"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativa
        substituir_por_decimal_br(self, "saldo_inicial", currency=True)

    def clean_nome(self):
        valor = (self.cleaned_data.get("nome") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome da conta.")
        return valor


class CategoriaFinanceiraForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = CategoriaFinanceira
        fields = ["nome", "tipo", "categoria_pai", "cor", "icone", "ativa"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativa"].widget = forms.HiddenInput()
        self.fields["ativa"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativa
        self.fields["icone"].required = False
        if user is not None:
            queryset = queryset_da_empresa(CategoriaFinanceira.objects.filter(ativa=True).order_by("tipo", "nome"), user)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            self.fields["categoria_pai"].queryset = queryset

    def clean_nome(self):
        valor = (self.cleaned_data.get("nome") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome da categoria.")
        return valor


class TransacaoForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = Transacao
        fields = [
            "tipo",
            "descricao",
            "valor",
            "data_competencia",
            "data_pagamento",
            "status",
            "conta",
            "conta_destino",
            "categoria",
            "observacoes",
        ]
        widgets = {
            "data_competencia": forms.DateInput(attrs={"type": "date"}),
            "data_pagamento": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor", currency=True)
        self.fields["observacoes"].widget.attrs["rows"] = 3
        self.fields["descricao"].error_messages["required"] = "Informe a descrição."
        if user is not None:
            self.fields["conta"].queryset = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), user)
            self.fields["conta_destino"].queryset = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), user)
            self.fields["categoria"].queryset = queryset_da_empresa(CategoriaFinanceira.objects.filter(ativa=True).order_by("tipo", "nome"), user)

    def clean_descricao(self):
        valor = (self.cleaned_data.get("descricao") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe a descrição.")
        return valor


class CartaoCreditoForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = CartaoCredito
        fields = ["nome", "bandeira", "limite", "dia_fechamento", "dia_vencimento", "conta_pagamento", "cor", "ativo"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativo"].widget = forms.HiddenInput()
        self.fields["ativo"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativo
        substituir_por_decimal_br(self, "limite", currency=True)
        if user is not None:
            self.fields["conta_pagamento"].queryset = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), user)

    def clean_nome(self):
        valor = (self.cleaned_data.get("nome") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome do cartão.")
        return valor


class FaturaCartaoForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = FaturaCartao
        fields = ["cartao", "mes", "ano", "data_fechamento", "data_vencimento", "status", "conta_pagamento", "categoria_pagamento"]
        widgets = {
            "data_fechamento": forms.DateInput(attrs={"type": "date"}),
            "data_vencimento": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [choice for choice in self.fields["status"].choices if choice[0] != "paga"]
        if user is not None:
            self.fields["cartao"].queryset = queryset_da_empresa(CartaoCredito.objects.filter(ativo=True).order_by("nome"), user)
            self.fields["conta_pagamento"].queryset = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), user)
            self.fields["categoria_pagamento"].queryset = queryset_da_empresa(CategoriaFinanceira.objects.filter(ativa=True, tipo="despesa").order_by("nome"), user)


class FaturaPagamentoForm(forms.Form):
    conta_pagamento = forms.ModelChoiceField(queryset=Conta.objects.none(), label="Conta de pagamento")
    categoria_pagamento = forms.ModelChoiceField(queryset=CategoriaFinanceira.objects.none(), label="Categoria")
    data_pagamento = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, user=None, fatura=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["conta_pagamento"].queryset = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), user)
            self.fields["categoria_pagamento"].queryset = queryset_da_empresa(CategoriaFinanceira.objects.filter(ativa=True, tipo="despesa").order_by("nome"), user)
        if fatura is not None:
            self.fields["conta_pagamento"].initial = fatura.conta_pagamento or fatura.cartao.conta_pagamento
            self.fields["categoria_pagamento"].initial = fatura.categoria_pagamento


class CompraCartaoForm(forms.Form):
    cartao = forms.ModelChoiceField(queryset=CartaoCredito.objects.none())
    categoria = forms.ModelChoiceField(queryset=CategoriaFinanceira.objects.none())
    descricao = forms.CharField(max_length=255)
    valor_total = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    data_compra = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    parcelas = forms.IntegerField(min_value=1, max_value=120, initial=1)
    mes_primeira_fatura = forms.IntegerField(min_value=1, max_value=12)
    ano_primeira_fatura = forms.IntegerField(min_value=2000, max_value=2100)
    observacoes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor_total", currency=True)
        if user is not None:
            self.fields["cartao"].queryset = queryset_da_empresa(CartaoCredito.objects.filter(ativo=True).order_by("nome"), user)
            self.fields["categoria"].queryset = queryset_da_empresa(CategoriaFinanceira.objects.filter(ativa=True, tipo="despesa").order_by("nome"), user)

    def valores_parcelas(self):
        valor_total = self.cleaned_data["valor_total"]
        parcelas = self.cleaned_data["parcelas"]
        valor_base = (valor_total / parcelas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        valores = [valor_base for _ in range(parcelas)]
        diferenca = valor_total - sum(valores, Decimal("0.00"))
        valores[-1] = (valores[-1] + diferenca).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return valores


class PlanejamentoMensalForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = PlanejamentoMensal
        fields = ["mes", "ano", "categoria", "valor_planejado"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor_planejado", currency=True)
        if user is not None:
            self.fields["categoria"].queryset = queryset_da_empresa(CategoriaFinanceira.objects.filter(ativa=True, tipo="despesa").order_by("nome"), user)


class MetaFinanceiraForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = MetaFinanceira
        fields = ["nome", "valor_alvo", "valor_atual_manual", "data_inicio", "data_limite", "conta_vinculada", "status", "cor", "observacoes"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_limite": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor_alvo", currency=True)
        substituir_por_decimal_br(self, "valor_atual_manual", currency=True)
        self.fields["observacoes"].widget.attrs["rows"] = 3
        if user is not None:
            self.fields["conta_vinculada"].queryset = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), user)


class RecorrenciaFinanceiraForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = RecorrenciaFinanceira
        fields = ["tipo", "descricao", "valor", "categoria", "conta", "frequencia", "dia_vencimento", "data_inicio", "data_fim", "ativa", "observacoes"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativa"].widget = forms.HiddenInput()
        self.fields["ativa"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativa
        substituir_por_decimal_br(self, "valor", currency=True)
        self.fields["observacoes"].widget.attrs["rows"] = 3
        if user is not None:
            self.fields["categoria"].queryset = queryset_da_empresa(CategoriaFinanceira.objects.filter(ativa=True).order_by("tipo", "nome"), user)
            self.fields["conta"].queryset = queryset_da_empresa(Conta.objects.filter(ativa=True).order_by("nome"), user)
