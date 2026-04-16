from django import forms


class OptimisticLockModelFormMixin(forms.ModelForm):
    concurrency_field_name = "concorrencia_atualizado_em"
    concurrency_model_field = "atualizado_em"
    concurrency_error_message = (
        "Este registro foi alterado em outra sessão. Recarregue a página para revisar os dados mais recentes."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.concurrency_field_name] = forms.CharField(
            required=False,
            widget=forms.HiddenInput(),
        )
        self.initial[self.concurrency_field_name] = self._serialize_concurrency_value(
            getattr(self.instance, self.concurrency_model_field, None)
        )

    def _serialize_concurrency_value(self, value):
        if value is None:
            return ""
        return value.isoformat(timespec="microseconds")

    def clean(self):
        cleaned_data = super().clean()
        if not getattr(self.instance, "pk", None):
            return cleaned_data
        if self.concurrency_field_name not in self.data:
            return cleaned_data

        submitted_value = (cleaned_data.get(self.concurrency_field_name) or "").strip()
        current_value = self._serialize_concurrency_value(
            getattr(self.instance, self.concurrency_model_field, None)
        )

        if not submitted_value or submitted_value != current_value:
            self.add_error(None, self.concurrency_error_message)

        return cleaned_data
