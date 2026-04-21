from django import forms
from django.utils import timezone

from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import substituir_por_decimal_br
from .models import Despesa, Receita, Reserva, arredondar


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
    valor_parcela = forms.DecimalField(max_digits=14, decimal_places=2, required=False, label="Valor da parcela")

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
        substituir_por_decimal_br(self, "valor_parcela", currency=True)
        self.fields["descricao"].widget.attrs["placeholder"] = "Ex.: mercado, aluguel, notebook"
        self.fields["data"].initial = self.fields["data"].initial or timezone.localdate()
        self.fields["parcelas"].required = False
        self.fields["parcelas"].widget.attrs["data-installments-input"] = "1"
        self.fields["valor"].widget.attrs["data-installments-total"] = "1"
        self.fields["valor_parcela"].widget.attrs["data-installments-unit"] = "1"
        if self.instance and self.instance.pk:
            self.fields["valor_parcela"].initial = self.instance.valor_parcela

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        parcelas = cleaned.get("parcelas") or 1
        valor_parcela = cleaned.get("valor_parcela")
        if tipo == "parcelada":
            if not parcelas:
                self.add_error("parcelas", "Informe a quantidade de parcelas.")
            elif parcelas < 2:
                self.add_error("parcelas", "Despesa parcelada precisa ter pelo menos 2 parcelas.")
            if valor_parcela and "valor_parcela" in self.changed_data:
                cleaned["valor"] = arredondar(valor_parcela * parcelas)
        else:
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
