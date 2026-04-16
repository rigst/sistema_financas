from django.contrib import admin

from .models import CategoriaFinanceira, Conta, CartaoCredito, MetaFinanceira, OrcamentoMensal, Transacao


@admin.register(Conta)
class ContaAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "instituicao", "saldo_inicial", "ativa", "empresa")
    list_filter = ("tipo", "ativa", "empresa")
    search_fields = ("nome", "instituicao")


@admin.register(CategoriaFinanceira)
class CategoriaFinanceiraAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "categoria_pai", "ativa", "empresa")
    list_filter = ("tipo", "ativa", "empresa")
    search_fields = ("nome",)


@admin.register(Transacao)
class TransacaoAdmin(admin.ModelAdmin):
    list_display = ("descricao", "tipo", "valor", "data_competencia", "status", "conta", "categoria", "empresa")
    list_filter = ("tipo", "status", "empresa", "data_competencia")
    search_fields = ("descricao", "observacoes")
    date_hierarchy = "data_competencia"


@admin.register(CartaoCredito)
class CartaoCreditoAdmin(admin.ModelAdmin):
    list_display = ("nome", "bandeira", "limite", "dia_fechamento", "dia_vencimento", "ativo", "empresa")
    list_filter = ("bandeira", "ativo", "empresa")
    search_fields = ("nome",)


@admin.register(OrcamentoMensal)
class OrcamentoMensalAdmin(admin.ModelAdmin):
    list_display = ("categoria", "mes", "ano", "valor_planejado", "empresa")
    list_filter = ("ano", "mes", "empresa")


@admin.register(MetaFinanceira)
class MetaFinanceiraAdmin(admin.ModelAdmin):
    list_display = ("nome", "valor_alvo", "valor_atual_manual", "status", "empresa")
    list_filter = ("status", "empresa")
    search_fields = ("nome",)
