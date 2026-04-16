from django import forms

from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import substituir_por_decimal_br
from core.tenancy import queryset_da_empresa
from .models import CategoriaFinanceira, Conta, Transacao


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
        widgets = {
            "data_saldo_inicial": forms.DateInput(attrs={"type": "date"}),
        }

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
