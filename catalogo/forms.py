import os
from pathlib import Path

from django import forms

from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import substituir_por_decimal_br
from core.tenancy import queryset_da_empresa
from .models import CategoriaItem, ItemCatalogo


class CategoriaItemForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = CategoriaItem
        fields = ["nome", "descricao", "cor", "ativo"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativo"].widget = forms.HiddenInput()
        self.fields["ativo"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativo
        self.fields["descricao"].widget.attrs["rows"] = 3

    def clean_nome(self):
        valor = (self.cleaned_data.get("nome") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome da categoria.")
        return valor


class ItemCatalogoForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = ItemCatalogo
        fields = [
            "codigo",
            "nome",
            "descricao_padrao",
            "categoria",
            "unidade_medida",
            "valor_unitario_padrao",
            "observacoes",
            "ativo",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativo"].widget = forms.HiddenInput()
        self.fields["ativo"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativo
        substituir_por_decimal_br(self, "valor_unitario_padrao", currency=True)
        self.fields["nome"].error_messages["required"] = "Informe o nome do item."
        self.fields["valor_unitario_padrao"].error_messages["min_value"] = "Informe um valor maior ou igual a zero."
        self.fields["codigo"].required = False
        self.fields["codigo"].widget.attrs.update(
            {
                "readonly": "readonly",
                "tabindex": "-1",
                "placeholder": "Gerado automaticamente pelo sistema",
            }
        )
        self.fields["descricao_padrao"].widget.attrs["rows"] = 3
        self.fields["observacoes"].widget.attrs["rows"] = 3
        if user is not None:
            self.fields["categoria"].queryset = queryset_da_empresa(
                CategoriaItem.objects.filter(ativo=True).order_by("nome"),
                user,
            )

    def clean_codigo(self):
        if self.instance.pk:
            return self.instance.codigo
        return (self.cleaned_data.get("codigo") or "").strip().upper()

    def clean_nome(self):
        valor = (self.cleaned_data.get("nome") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome do item.")
        return valor


class ImportarCatalogoExcelForm(forms.Form):
    arquivo = forms.FileField(help_text="Envie um arquivo .xlsx com cabeçalho na primeira linha.")

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        extensao = Path(arquivo.name or "").suffix.lower()
        if extensao and extensao != ".xlsx":
            raise forms.ValidationError("Envie um arquivo com extensão .xlsx.")

        max_bytes = max(int(os.getenv("DJANGO_MAX_CATALOGO_UPLOAD_BYTES", str(5 * 1024 * 1024))), 1)
        if arquivo.size > max_bytes:
            raise forms.ValidationError("Arquivo excede o tamanho máximo permitido (5 MB).")

        return arquivo
