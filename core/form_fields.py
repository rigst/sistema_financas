from django import forms
from django.core.exceptions import ValidationError

from .formatting import (
    formatar_cep_br,
    formatar_cpf_cnpj_br,
    formatar_decimal_br,
    formatar_moeda_br,
    formatar_telefone_br,
    parse_decimal_br,
)


class DecimalBRField(forms.DecimalField):
    def __init__(self, *args, currency=False, **kwargs):
        self.currency = currency
        super().__init__(*args, **kwargs)
        self.widget = forms.TextInput(
            attrs={
                **self.widget.attrs,
                "inputmode": "decimal",
                "autocomplete": "off",
                "data-br-currency": "1" if self.currency else "0",
                "data-br-decimal": "1",
                "data-decimal-places": str(self.decimal_places or 2),
            }
        )

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return parse_decimal_br(value)
        except ValueError as exc:
            raise ValidationError(self.error_messages["invalid"], code="invalid") from exc

    def prepare_value(self, value):
        if value in self.empty_values:
            return ""
        try:
            if self.currency:
                return formatar_moeda_br(value)
            return formatar_decimal_br(value, casas=self.decimal_places or 2)
        except (ValueError, TypeError):
            return super().prepare_value(value)


def substituir_por_decimal_br(form, nome_campo, *, currency=False):
    campo_original = form.fields[nome_campo]
    novo_campo = DecimalBRField(
        required=campo_original.required,
        label=campo_original.label,
        help_text=campo_original.help_text,
        initial=campo_original.initial,
        disabled=campo_original.disabled,
        min_value=getattr(campo_original, "min_value", None),
        max_value=getattr(campo_original, "max_value", None),
        max_digits=getattr(campo_original, "max_digits", None),
        decimal_places=getattr(campo_original, "decimal_places", 2),
        validators=campo_original.validators,
        error_messages=campo_original.error_messages.copy(),
        currency=currency,
    )
    novo_campo.widget.attrs.update(campo_original.widget.attrs)
    novo_campo.widget.attrs["inputmode"] = "decimal"
    novo_campo.widget.attrs["autocomplete"] = "off"
    novo_campo.widget.attrs["data-br-currency"] = "1" if currency else "0"
    novo_campo.widget.attrs["data-br-decimal"] = "1"
    novo_campo.widget.attrs["data-decimal-places"] = str(novo_campo.decimal_places or 2)
    form.fields[nome_campo] = novo_campo


def configurar_campo_mascarado(form, nome_campo, tipo_mascara, *, placeholder=""):
    campo = form.fields[nome_campo]
    campo.widget.attrs["autocomplete"] = "off"
    campo.widget.attrs["data-br-mask"] = tipo_mascara
    if placeholder:
        campo.widget.attrs.setdefault("placeholder", placeholder)

    if form.is_bound:
        return

    valor_inicial = form.initial.get(nome_campo)
    if valor_inicial in (None, "") and getattr(form, "instance", None) is not None:
        valor_inicial = getattr(form.instance, nome_campo, None)

    if valor_inicial in (None, ""):
        return

    if tipo_mascara == "cpf_cnpj":
        form.initial[nome_campo] = formatar_cpf_cnpj_br(valor_inicial)
    elif tipo_mascara == "phone":
        form.initial[nome_campo] = formatar_telefone_br(valor_inicial)
    elif tipo_mascara == "cep":
        form.initial[nome_campo] = formatar_cep_br(valor_inicial)
