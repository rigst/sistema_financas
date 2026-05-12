import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import substituir_por_decimal_br
from .models import CompartilhamentoDespesa, Despesa, Receita, Reserva, arredondar, normalizar_competencia


def _parse_decimal_br(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _parse_decimal_list_br(valor, esperado):
    texto = str(valor or "").strip()
    if not texto:
        return []
    if ";" in texto:
        return [_parse_decimal_br(item) for item in texto.split(";") if item.strip()]
    padrao_monetario = r"\d+(?:\.\d{3})*,\d{1,2}|\d+(?:\.\d{3})+|\d+"
    encontrados = re.findall(padrao_monetario, texto)
    if len(encontrados) == esperado:
        return [_parse_decimal_br(item) for item in encontrados]
    return [_parse_decimal_br(item) for item in texto.split(",") if item.strip()]


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
    compartilhar = forms.BooleanField(required=False, label="Compartilhar despesa")
    participantes = forms.CharField(required=False, label="Compartilhar com", help_text="Separe usuários por vírgula.")
    modo_divisao = forms.ChoiceField(choices=CompartilhamentoDespesa.MODO_CHOICES, required=False, label="Divisão")
    valores_participantes = forms.CharField(required=False, label="Valores dos participantes", help_text="Na mesma ordem dos usuários, separados por vírgula.")
    pagador = forms.CharField(required=False, label="Quem pagou ou vai pagar")
    data_prevista_ressarcimento = forms.DateField(
        required=False,
        label="Data prevista para ressarcimento",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    class Meta:
        model = Despesa
        fields = ["tipo", "descricao", "valor", "data", "competencia", "categoria", "parcelas", "parcela_atual", "status", "observacoes"]
        widgets = {
            "tipo": forms.Select(attrs={"data-expense-type": "1"}),
            "data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor", currency=True)
        substituir_por_decimal_br(self, "valor_parcela", currency=True)
        self.fields["descricao"].widget.attrs["placeholder"] = "Ex.: mercado, aluguel, notebook"
        self.fields["compartilhar"].widget.attrs["data-shared-toggle"] = "1"
        self.fields["participantes"].widget.attrs["placeholder"] = "Ex.: joao, maria"
        self.fields["modo_divisao"].widget.attrs["data-shared-mode"] = "1"
        self.fields["valores_participantes"].widget.attrs["placeholder"] = "Ex.: 120,00; 80,00"
        self.fields["valores_participantes"].widget.attrs["data-shared-values"] = "1"
        self.fields["pagador"].widget.attrs["placeholder"] = f"Ex.: {user.username}" if user else "Ex.: usuario"
        self.fields["pagador"].initial = self.initial.get("pagador") or getattr(user, "username", "")
        self.categorias_sugeridas = []
        self.usuarios_sugeridos = []
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
            User = get_user_model()
            self.usuarios_sugeridos = list(
                User.objects.filter(is_active=True)
                .exclude(pk=user.pk)
                .order_by("username")
                .values_list("username", flat=True)[:100]
            )
            if self.usuarios_sugeridos:
                self.fields["participantes"].widget.attrs["list"] = "usuarios-sistema"
                self.fields["pagador"].widget.attrs["list"] = "usuarios-sistema-com-criador"
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
            try:
                compartilhamento = self.instance.compartilhamento
            except CompartilhamentoDespesa.DoesNotExist:
                compartilhamento = None
            if compartilhamento:
                participantes = list(compartilhamento.participantes.select_related("usuario").all())
                self.fields["compartilhar"].initial = True
                self.fields["participantes"].initial = ", ".join(item.usuario.username for item in participantes)
                self.fields["modo_divisao"].initial = compartilhamento.modo_divisao
                self.fields["valores_participantes"].initial = ", ".join(str(item.valor).replace(".", ",") for item in participantes)
                self.fields["pagador"].initial = compartilhamento.pagador.username
                self.fields["data_prevista_ressarcimento"].initial = compartilhamento.data_prevista_ressarcimento
                self.fields["valor"].initial = compartilhamento.valor_total
                if self.instance.tipo == "parcelada":
                    self.fields["valor_parcela"].initial = arredondar(compartilhamento.valor_total / self.instance.parcelas)

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
        self._clean_compartilhamento(cleaned)
        return cleaned

    def _clean_compartilhamento(self, cleaned):
        if not cleaned.get("compartilhar"):
            cleaned["participantes_resolvidos"] = []
            cleaned["pagador_resolvido"] = None
            return

        User = get_user_model()
        nomes = [nome.strip() for nome in str(cleaned.get("participantes") or "").split(",") if nome.strip()]
        if not nomes:
            self.add_error("participantes", "Informe pelo menos um usuário para compartilhar.")
            return
        if self.user and self.user.username in nomes:
            self.add_error("participantes", "Não inclua seu próprio usuário na lista de participantes.")
            return

        usuarios = list(User.objects.filter(username__in=nomes, is_active=True))
        encontrados = {usuario.username: usuario for usuario in usuarios}
        ausentes = [nome for nome in nomes if nome not in encontrados]
        if ausentes:
            self.add_error("participantes", f"Usuário(s) não encontrado(s): {', '.join(ausentes)}.")
            return
        participantes = [encontrados[nome] for nome in nomes]

        pagador_nome = (cleaned.get("pagador") or "").strip()
        if not pagador_nome:
            self.add_error("pagador", "Informe quem pagou ou vai pagar.")
            return
        pagador = self.user if self.user and pagador_nome == self.user.username else encontrados.get(pagador_nome)
        if not pagador:
            self.add_error("pagador", "O pagador deve ser o criador ou um dos participantes informados.")
            return

        valor_total = cleaned.get("valor")
        if not valor_total:
            return
        modo = cleaned.get("modo_divisao") or "igual"
        if modo == "fixo":
            valores = _parse_decimal_list_br(cleaned.get("valores_participantes"), len(participantes))
            if len(valores) != len(participantes) or any(valor is None or valor <= 0 for valor in valores):
                self.add_error("valores_participantes", "Informe um valor positivo para cada participante, na mesma ordem.")
                return
            soma_participantes = arredondar(sum(valores, Decimal("0.00")))
            valor_criador = arredondar(valor_total - soma_participantes)
            if valor_criador <= 0:
                self.add_error("valores_participantes", "A soma dos participantes deve ser menor que o valor total.")
                return
        else:
            quantidade = Decimal(len(participantes) + 1)
            valores = [arredondar(valor_total / quantidade) for _usuario in participantes]
            valor_criador = arredondar(valor_total - sum(valores, Decimal("0.00")))

        cleaned["participantes_resolvidos"] = list(zip(participantes, valores))
        cleaned["pagador_resolvido"] = pagador
        cleaned["valor_criador_compartilhado"] = valor_criador


class ReservaForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = Reserva
        fields = ["nome", "valor_atual", "valor_alvo", "observacoes"]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor_atual", currency=True)
        substituir_por_decimal_br(self, "valor_alvo", currency=True)
