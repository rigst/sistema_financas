from django.urls import path

from .views import (
    configuracao_criar,
    configuracao_editar,
    configuracao_excluir,
    configuracao_logo,
    configuracao_lista,
    configuracao_visualizar,
    orcamento_exportar_memorial_pdf,
    orcamento_exportar_memorial_word,
    orcamento_exportar_excel,
    orcamento_exportar_pdf,
    orcamento_relatorio_central,
)

app_name = "relatorios"

urlpatterns = [
    path("configuracoes/", configuracao_lista, name="configuracao_lista"),
    path("configuracoes/nova/", configuracao_criar, name="configuracao_criar"),
    path("configuracoes/<int:pk>/", configuracao_visualizar, name="configuracao_visualizar"),
    path("configuracoes/<int:pk>/logo/", configuracao_logo, name="configuracao_logo"),
    path("configuracoes/<int:pk>/editar/", configuracao_editar, name="configuracao_editar"),
    path("configuracoes/<int:pk>/excluir/", configuracao_excluir, name="configuracao_excluir"),
    path("orcamentos/<int:pk>/", orcamento_relatorio_central, name="orcamento_central"),
    path("orcamentos/<int:pk>/excel/", orcamento_exportar_excel, name="orcamento_excel"),
    path("orcamentos/<int:pk>/pdf/", orcamento_exportar_pdf, name="orcamento_pdf"),
    path("orcamentos/<int:pk>/memorial-descritivo/pdf/", orcamento_exportar_memorial_pdf, name="orcamento_memorial_pdf"),
    path("orcamentos/<int:pk>/memorial-descritivo/word/", orcamento_exportar_memorial_word, name="orcamento_memorial_word"),
]
