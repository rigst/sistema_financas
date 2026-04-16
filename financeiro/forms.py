from django import forms
from django.utils import timezone

from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import substituir_por_decimal_br
from .models import Despesa, Receita, Reserva


class ReceitaSimplificadaForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = Receita
        fields = ["descricao", "valor", "data", "categoria", "status", "observacoes"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor", currency=True)
        self.fields["descricao"].widget.attrs["placeholder"] = "Ex.: salário, venda, reembolso"
        self.fields["data"].initial = self.fields["data"].initial or timezone.localdate()


class DespesaSimplificadaForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = Despesa
        fields = ["tipo", "descricao", "valor", "data", "categoria", "parcelas", "status", "observacoes"]
        widgets = {
            "tipo": forms.Select(attrs={"data-expense-type": "1"}),
            "data": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor", currency=True)
        self.fields["descricao"].widget.attrs["placeholder"] = "Ex.: mercado, aluguel, notebook"
        self.fields["data"].initial = self.fields["data"].initial or timezone.localdate()
        self.fields["parcelas"].required = False
        self.fields["parcelas"].widget.attrs["data-installments-input"] = "1"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("tipo") == "parcelada" and not cleaned.get("parcelas"):
            self.add_error("parcelas", "Informe a quantidade de parcelas.")
        if cleaned.get("tipo") != "parcelada":
            cleaned["parcelas"] = 1
        return cleaned


class ReservaForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = Reserva
        fields = ["nome", "valor_atual", "valor_alvo", "observacoes"]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor_atual", currency=True)
        substituir_por_decimal_br(self, "valor_alvo", currency=True)
