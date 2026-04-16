import re
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils.timezone import localdate

from catalogo.models import ItemCatalogo
from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import configurar_campo_mascarado, substituir_por_decimal_br
from core.formatting import formatar_cep_br, formatar_cpf_cnpj_br, formatar_telefone_br
from core.validators import validar_cep_basico, validar_cpf_cnpj_basico, validar_telefone_basico
from .models import ItemOrcamento, Orcamento


def calcular_validade_inicial_configuracao(configuracao, data_emissao):
    texto = str(getattr(configuracao, "validade_padrao_proposta", "") or "").strip()
    correspondencia = re.search(r"\d+", texto)
    if not correspondencia or not data_emissao:
        return None
    try:
        dias = int(correspondencia.group())
    except (TypeError, ValueError):
        return None
    return data_emissao + timedelta(days=dias)


class OrcamentoForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = [
            "numero",
            "configuracao_empresa",
            "cliente",
            "titulo",
            "descricao_inicial",
            "observacoes_gerais",
            "status",
            "data_emissao",
            "validade_em",
            "evento_nome",
            "evento_periodo",
            "evento_local",
            "evento_estande",
            "evento_area",
            "evento_contato",
            "evento_telefone",
            "evento_email",
            "desconto_global_valor",
            "desconto_global_percentual",
            "acrescimo_global_valor",
            "acrescimo_global_percentual",
            "condicoes_pagamento",
            "valor_locacao",
            "valor_servico",
            "servicos_taxas_inclusos",
            "contrato_razao_social",
            "contrato_cnpj",
            "contrato_endereco",
            "contrato_cidade",
            "contrato_cep",
            "contrato_responsavel_nome",
            "contrato_responsavel_documento",
            "contrato_cargo_funcao",
            "contrato_telefone",
            "contrato_email",
            "contrato_inscricao_estadual",
        ]
        widgets = {
            "data_emissao": forms.DateInput(attrs={"type": "date"}),
            "validade_em": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        placeholders = {
            "numero": "Gerado automaticamente pelo sistema",
            "titulo": "Ex.: Orçamento de reforma da recepção",
            "descricao_inicial": "Resumo inicial do orçamento",
            "observacoes_gerais": "Observações internas ou gerais",
            "evento_nome": "Ex.: Expointer 2026",
            "evento_periodo": "Ex.: de 24/08 a 01/09/2026",
            "evento_local": "Ex.: Esteio - RS",
            "evento_estande": "Ex.: 562",
            "evento_area": "Ex.: 1.250m²",
            "evento_contato": "Nome dos contatos do projeto",
            "evento_email": "contato@cliente.com.br",
            "desconto_global_valor": "0.00",
            "desconto_global_percentual": "0.00",
            "acrescimo_global_valor": "0.00",
            "acrescimo_global_percentual": "0.00",
            "condicoes_pagamento": "Descreva as condições comerciais",
            "valor_locacao": "0.00",
            "valor_servico": "0.00",
            "servicos_taxas_inclusos": "Liste serviços e taxas inclusos",
            "contrato_razao_social": "Razão social para contrato",
            "contrato_cnpj": "00.000.000/0000-00",
            "contrato_endereco": "Endereço completo",
            "contrato_cidade": "Cidade",
            "contrato_cep": "00000-000",
            "contrato_responsavel_nome": "Responsável pela assinatura",
            "contrato_responsavel_documento": "RG e CPF do responsável",
            "contrato_cargo_funcao": "Cargo ou função",
            "contrato_telefone": "(00) 00000-0000",
            "contrato_email": "contrato@cliente.com.br",
            "contrato_inscricao_estadual": "Inscrição estadual",
        }

        for nome, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.DateInput, forms.Textarea)):
                widget.attrs.setdefault("placeholder", placeholders.get(nome, ""))

        self.fields["numero"].required = False
        self.fields["data_emissao"].required = False
        self.fields["numero"].widget.attrs.update(
            {
                "readonly": "readonly",
                "tabindex": "-1",
            }
        )

        for nome_campo in [
            "desconto_global_valor",
            "desconto_global_percentual",
            "acrescimo_global_valor",
            "acrescimo_global_percentual",
            "valor_locacao",
            "valor_servico",
        ]:
            self.fields[nome_campo].required = False
            substituir_por_decimal_br(self, nome_campo, currency=nome_campo.endswith("_valor"))

        configurar_campo_mascarado(self, "evento_telefone", "phone", placeholder="(00) 00000-0000")
        configurar_campo_mascarado(self, "contrato_cnpj", "cpf_cnpj", placeholder="00.000.000/0000-00")
        configurar_campo_mascarado(self, "contrato_telefone", "phone", placeholder="(00) 00000-0000")
        configurar_campo_mascarado(self, "contrato_cep", "cep", placeholder="00000-000")
        for nome in [
            "descricao_inicial",
            "observacoes_gerais",
            "condicoes_pagamento",
            "servicos_taxas_inclusos",
        ]:
            self.fields[nome].widget.attrs["rows"] = 3
        if not self.instance.pk and not self.is_bound:
            self.fields["data_emissao"].initial = localdate()
        if user is not None:
            from clientes.models import Cliente
            from core.tenancy import queryset_da_empresa
            from relatorios.models import ConfiguracaoEmpresa
            from django.db.models import Q

            self.fields["cliente"].queryset = queryset_da_empresa(Cliente.objects.filter(ativo=True).order_by("nome_razao_social"), user)
            configuracoes = queryset_da_empresa(ConfiguracaoEmpresa.objects.all(), user)
            if self.instance.pk and self.instance.configuracao_empresa_id:
                configuracoes = configuracoes.filter(Q(ativo=True) | Q(pk=self.instance.configuracao_empresa_id))
            else:
                configuracoes = configuracoes.filter(ativo=True)
            configuracoes = configuracoes.order_by("nome_empresa", "-atualizado_em")
            self.fields["configuracao_empresa"].queryset = configuracoes
            self.fields["configuracao_empresa"].required = False

            if not self.instance.pk and not self.is_bound:
                configuracao_inicial = configuracoes.first()
                if configuracao_inicial:
                    self.initial.setdefault("configuracao_empresa", configuracao_inicial.pk)
                    self.fields["configuracao_empresa"].initial = configuracao_inicial.pk
                    data_emissao_inicial = self.fields["data_emissao"].initial or localdate()
                    validade_inicial = calcular_validade_inicial_configuracao(configuracao_inicial, data_emissao_inicial)
                    if validade_inicial and not self.initial.get("validade_em"):
                        self.initial["validade_em"] = validade_inicial
                        self.fields["validade_em"].initial = validade_inicial

    def clean_evento_telefone(self):
        valor = (self.cleaned_data.get("evento_telefone") or "").strip()
        if not valor:
            return ""
        validar_telefone_basico(valor, campo="Telefone do evento")
        return formatar_telefone_br(valor)

    def clean(self):
        cleaned_data = super().clean()
        configuracao = cleaned_data.get("configuracao_empresa")
        validade_em = cleaned_data.get("validade_em")
        data_emissao = cleaned_data.get("data_emissao") or localdate()
        cleaned_data["data_emissao"] = data_emissao
        if configuracao and not validade_em:
            validade_calculada = calcular_validade_inicial_configuracao(configuracao, data_emissao)
            if validade_calculada:
                cleaned_data["validade_em"] = validade_calculada
        return cleaned_data

    def clean_contrato_cnpj(self):
        valor = (self.cleaned_data.get("contrato_cnpj") or "").strip()
        if not valor:
            return ""
        validar_cpf_cnpj_basico(valor)
        return formatar_cpf_cnpj_br(valor)

    def clean_contrato_telefone(self):
        valor = (self.cleaned_data.get("contrato_telefone") or "").strip()
        if not valor:
            return ""
        validar_telefone_basico(valor, campo="Telefone contratual")
        return formatar_telefone_br(valor)

    def clean_contrato_cep(self):
        valor = (self.cleaned_data.get("contrato_cep") or "").strip()
        if not valor:
            return ""
        validar_cep_basico(valor)
        return formatar_cep_br(valor)


class ItemOrcamentoForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = ItemOrcamento
        fields = [
            "item_catalogo",
            "ordem",
            "codigo_item",
            "nome",
            "descricao",
            "unidade_medida",
            "quantidade",
            "valor_unitario",
            "desconto_valor",
            "desconto_percentual",
            "acrescimo_valor",
            "acrescimo_percentual",
            "observacoes",
        ]
        widgets = {
            "descricao": forms.Textarea(),
            "observacoes": forms.Textarea(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = ItemCatalogo.objects.filter(ativo=True).select_related("categoria").order_by("nome")
        if user is not None:
            from core.tenancy import queryset_da_empresa

            queryset = queryset_da_empresa(queryset, user)
        self.fields["item_catalogo"].queryset = queryset
        self.fields["item_catalogo"].required = False
        self.fields["nome"].required = False
        self.fields["unidade_medida"].required = False
        self.fields["ordem"].required = False
        for nome_campo in [
            "quantidade",
            "valor_unitario",
            "desconto_valor",
            "desconto_percentual",
            "acrescimo_valor",
            "acrescimo_percentual",
        ]:
            if nome_campo != "quantidade" and nome_campo != "valor_unitario":
                self.fields[nome_campo].required = False
            substituir_por_decimal_br(self, nome_campo, currency=nome_campo.endswith("_valor") or nome_campo == "valor_unitario")
        self.fields["valor_unitario"].required = False

        self.fields["codigo_item"].required = False
        self.fields["codigo_item"].widget.attrs.update(
            {
                "readonly": "readonly",
                "tabindex": "-1",
                "placeholder": "Gerado automaticamente pelo sistema",
            }
        )
        self.fields["ordem"].widget = forms.HiddenInput()
        self.fields["codigo_item"].widget = forms.HiddenInput()
        self.fields["nome"].widget = forms.HiddenInput()
        self.fields["unidade_medida"].widget = forms.HiddenInput()
        self.fields["descricao"].widget.attrs["rows"] = 2
        self.fields["observacoes"].widget = forms.HiddenInput()

    def aplicar_defaults_catalogo(self, cleaned_data):
        item_catalogo = cleaned_data.get("item_catalogo")

        if item_catalogo:
            if not cleaned_data.get("nome"):
                cleaned_data["nome"] = item_catalogo.nome
            if not cleaned_data.get("descricao"):
                cleaned_data["descricao"] = item_catalogo.descricao_padrao
            if not cleaned_data.get("unidade_medida"):
                cleaned_data["unidade_medida"] = item_catalogo.unidade_medida

            valor_unitario = cleaned_data.get("valor_unitario")
            if valor_unitario is None:
                cleaned_data["valor_unitario"] = item_catalogo.valor_unitario_padrao

        return cleaned_data

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data = self.aplicar_defaults_catalogo(cleaned_data)

        if not cleaned_data.get("item_catalogo") and not cleaned_data.get("nome"):
            self.add_error("item_catalogo", "Este campo é obrigatório.")

        if not cleaned_data.get("unidade_medida"):
            self.add_error("unidade_medida", "Este campo é obrigatório.")
        if cleaned_data.get("valor_unitario") is None:
            self.add_error("valor_unitario", "Este campo é obrigatório.")

        return cleaned_data

    def construir_item_preview(self, orcamento):
        cleaned_data = self.aplicar_defaults_catalogo(dict(self.cleaned_data))
        item = ItemOrcamento(
            orcamento=orcamento,
            item_catalogo=cleaned_data.get("item_catalogo"),
            ordem=cleaned_data.get("ordem") or 1,
            codigo_item=cleaned_data.get("codigo_item") or "",
            nome=cleaned_data.get("nome") or "Prévia",
            descricao=cleaned_data.get("descricao") or "",
            unidade_medida=cleaned_data.get("unidade_medida") or "un",
            quantidade=cleaned_data.get("quantidade") or 1,
            valor_unitario=cleaned_data.get("valor_unitario") or 0,
            desconto_valor=cleaned_data.get("desconto_valor") or 0,
            desconto_percentual=cleaned_data.get("desconto_percentual") or 0,
            acrescimo_valor=cleaned_data.get("acrescimo_valor") or 0,
            acrescimo_percentual=cleaned_data.get("acrescimo_percentual") or 0,
            observacoes=cleaned_data.get("observacoes") or "",
        )

        erro_validacao = None
        try:
            item.clean()
        except ValidationError as exc:
            if hasattr(exc, "messages"):
                erro_validacao = " ".join(exc.messages)
            else:
                erro_validacao = str(exc)

        item.subtotal = item.calcular_subtotal()
        item.divergencias_catalogo = item.campos_divergentes_catalogo()
        return item, erro_validacao
