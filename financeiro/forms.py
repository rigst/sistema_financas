from django import forms
from django.utils import timezone

from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import substituir_por_decimal_br
from .models import Despesa, Receita, Reserva, arredondar, normalizar_competencia


class CompetenciaMonthInput(forms.DateInput):
    input_type = "month"

    def format_value(self, value):
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m")
        if isinstance(value, str) and len(value) >= 7:
            return value[:7]
        return super().format_value(value)


class CompetenciaField(forms.DateField):
    widget = CompetenciaMonthInput

    def to_python(self, value):
        if isinstance(value, str) and len(value) == 7:
            value = f"{value}-01"
        parsed = super().to_python(value)
        if parsed:
            return parsed.replace(day=1)
        return parsed


class ReceitaSimplificadaForm(OptimisticLockModelFormMixin, forms.ModelForm):
    valor_parcela = forms.DecimalField(max_digits=14, decimal_places=2, required=False, label="Valor da parcela")
    competencia = CompetenciaField(label="Competência", required=False)

    class Meta:
        model = Receita
        fields = ["tipo", "descricao", "valor", "data", "competencia", "categoria", "parcelas", "parcela_atual", "status", "observacoes"]
        widgets = {
            "tipo": forms.Select(attrs={"data-expense-type": "1", "data-income-type": "1"}),
            "data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor", currency=True)
        substituir_por_decimal_br(self, "valor_parcela", currency=True)
        self.fields["descricao"].widget.attrs["placeholder"] = "Ex.: salário, venda, reembolso"
        hoje = timezone.localdate()
        self.fields["data"].initial = self.initial.get("data") or getattr(self.instance, "data", None) or hoje
        self.fields["competencia"].initial = self.initial.get("competencia") or getattr(self.instance, "competencia", None) or self.fields["data"].initial
        self.fields["parcelas"].required = False
        self.fields["parcelas"].label = "Total de parcelas"
        self.fields["parcela_atual"].required = False
        self.fields["parcela_atual"].label = "Parcela atual"
        self.fields["parcela_atual"].initial = self.initial.get("parcela_atual") or getattr(self.instance, "parcela_atual", None) or 1
        self.fields["parcelas"].widget.attrs["data-installments-input"] = "1"
        self.fields["parcela_atual"].widget.attrs["data-installments-current"] = "1"
        self.fields["valor"].widget.attrs["data-installments-total"] = "1"
        self.fields["valor_parcela"].widget.attrs["data-installments-unit"] = "1"
        if self.instance and self.instance.pk:
            self.fields["valor_parcela"].initial = self.instance.valor_parcela

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        parcelas = cleaned.get("parcelas") or 1
        parcela_atual = cleaned.get("parcela_atual") or 1
        valor_parcela = cleaned.get("valor_parcela")
        if tipo == "parcelada":
            if not parcelas:
                self.add_error("parcelas", "Informe a quantidade de parcelas.")
            elif parcelas < 2:
                self.add_error("parcelas", "Receita parcelada precisa ter pelo menos 2 parcelas.")
            if parcela_atual > parcelas:
                self.add_error("parcela_atual", "A parcela atual não pode ser maior que o total de parcelas.")
            if valor_parcela and "valor_parcela" in self.changed_data:
                cleaned["valor"] = arredondar(valor_parcela * parcelas)
        else:
            cleaned["parcelas"] = 1
            cleaned["parcela_atual"] = 1
        if not cleaned.get("competencia"):
            cleaned["competencia"] = cleaned.get("data")
        cleaned["competencia"] = normalizar_competencia(cleaned.get("competencia"))
        return cleaned


class DespesaSimplificadaForm(OptimisticLockModelFormMixin, forms.ModelForm):
    valor_parcela = forms.DecimalField(max_digits=14, decimal_places=2, required=False, label="Valor da parcela")
    competencia = CompetenciaField(label="Competência", required=False)

    class Meta:
        model = Despesa
        fields = ["tipo", "descricao", "valor", "data", "competencia", "categoria", "parcelas", "parcela_atual", "status", "observacoes"]
        widgets = {
            "tipo": forms.Select(attrs={"data-expense-type": "1"}),
            "data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor", currency=True)
        substituir_por_decimal_br(self, "valor_parcela", currency=True)
        self.fields["descricao"].widget.attrs["placeholder"] = "Ex.: mercado, aluguel, notebook"
        self.categorias_sugeridas = []
        if user and getattr(user, "is_authenticated", False):
            self.categorias_sugeridas = list(
                Despesa.objects.filter(criado_por=user)
                .exclude(categoria="")
                .order_by("categoria")
                .values_list("categoria", flat=True)
                .distinct()
            )
            if self.categorias_sugeridas:
                self.fields["categoria"].widget.attrs["list"] = "categorias-despesa"
        hoje = timezone.localdate()
        self.fields["data"].initial = self.initial.get("data") or getattr(self.instance, "data", None) or hoje
        self.fields["competencia"].initial = self.initial.get("competencia") or getattr(self.instance, "competencia", None) or self.fields["data"].initial
        self.fields["parcelas"].required = False
        self.fields["parcelas"].label = "Total de parcelas"
        self.fields["parcela_atual"].required = False
        self.fields["parcela_atual"].label = "Parcela atual"
        self.fields["parcela_atual"].initial = self.initial.get("parcela_atual") or getattr(self.instance, "parcela_atual", None) or 1
        self.fields["status"].required = False
        self.fields["status"].initial = self.initial.get("status") or getattr(self.instance, "status", None) or "pendente"
        self.fields["parcelas"].widget.attrs["data-installments-input"] = "1"
        self.fields["parcela_atual"].widget.attrs["data-installments-current"] = "1"
        self.fields["valor"].widget.attrs["data-installments-total"] = "1"
        self.fields["valor_parcela"].widget.attrs["data-installments-unit"] = "1"
        if self.instance and self.instance.pk:
            self.fields["valor_parcela"].initial = self.instance.valor_parcela

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        parcelas = cleaned.get("parcelas") or 1
        parcela_atual = cleaned.get("parcela_atual") or 1
        valor_parcela = cleaned.get("valor_parcela")
        if tipo == "parcelada":
            if not parcelas:
                self.add_error("parcelas", "Informe a quantidade de parcelas.")
            elif parcelas < 2:
                self.add_error("parcelas", "Despesa parcelada precisa ter pelo menos 2 parcelas.")
            if parcela_atual > parcelas:
                self.add_error("parcela_atual", "A parcela atual não pode ser maior que o total de parcelas.")
            if valor_parcela and "valor_parcela" in self.changed_data:
                cleaned["valor"] = arredondar(valor_parcela * parcelas)
        else:
            cleaned["parcelas"] = 1
            cleaned["parcela_atual"] = 1
        if not cleaned.get("competencia"):
            cleaned["competencia"] = cleaned.get("data")
        cleaned["competencia"] = normalizar_competencia(cleaned.get("competencia"))
        if not cleaned.get("status"):
            cleaned["status"] = "pendente"
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
