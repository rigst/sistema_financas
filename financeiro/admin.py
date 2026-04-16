from django.contrib import admin

from core.admin_permissions import PerfilAdminPermissionMixin

from .models import (
    CategoriaFinanceira,
    Conta,
    CartaoCredito,
    FaturaCartao,
    LancamentoCartao,
    MetaFinanceira,
    PlanejamentoMensal,
    RecorrenciaFinanceira,
    Transacao,
)


class FinanceiroAdminMixin(PerfilAdminPermissionMixin):
    capability_view = "pode_visualizar_financeiro"
    capability_add = "pode_gerenciar_financeiro"
    capability_change = "pode_gerenciar_financeiro"
    capability_delete = "pode_gerenciar_financeiro"


@admin.register(Conta)
class ContaAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "tipo", "instituicao", "saldo_inicial", "ativa", "empresa")
    list_filter = ("tipo", "ativa", "empresa")
    search_fields = ("nome", "instituicao")


@admin.register(CategoriaFinanceira)
class CategoriaFinanceiraAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "tipo", "categoria_pai", "ativa", "empresa")
    list_filter = ("tipo", "ativa", "empresa")
    search_fields = ("nome",)


@admin.register(Transacao)
class TransacaoAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("descricao", "tipo", "valor", "data_competencia", "status", "conta", "categoria", "empresa")
    list_filter = ("tipo", "status", "empresa", "data_competencia")
    search_fields = ("descricao", "observacoes")
    date_hierarchy = "data_competencia"


@admin.register(CartaoCredito)
class CartaoCreditoAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "bandeira", "limite", "dia_fechamento", "dia_vencimento", "ativo", "empresa")
    list_filter = ("bandeira", "ativo", "empresa")
    search_fields = ("nome",)


@admin.register(FaturaCartao)
class FaturaCartaoAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("cartao", "mes", "ano", "status", "data_vencimento", "conta_pagamento", "empresa")
    list_filter = ("status", "ano", "mes", "empresa")
    search_fields = ("cartao__nome",)


@admin.register(LancamentoCartao)
class LancamentoCartaoAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("descricao", "cartao", "fatura", "categoria", "valor", "data_compra", "status", "empresa")
    list_filter = ("status", "cartao", "categoria", "empresa")
    search_fields = ("descricao", "observacoes")
    date_hierarchy = "data_compra"


@admin.register(PlanejamentoMensal)
class PlanejamentoMensalAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("categoria", "mes", "ano", "valor_planejado", "empresa")
    list_filter = ("ano", "mes", "empresa")


@admin.register(MetaFinanceira)
class MetaFinanceiraAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "valor_alvo", "valor_atual_manual", "status", "empresa")
    list_filter = ("status", "empresa")
    search_fields = ("nome",)


@admin.register(RecorrenciaFinanceira)
class RecorrenciaFinanceiraAdmin(FinanceiroAdminMixin, admin.ModelAdmin):
    list_display = ("descricao", "tipo", "valor", "frequencia", "dia_vencimento", "ativa", "empresa")
    list_filter = ("tipo", "frequencia", "ativa", "empresa")
    search_fields = ("descricao", "observacoes")
