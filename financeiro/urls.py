from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("receitas/", views.receita_lista, name="receita_lista"),
    path("receitas/nova/", views.receita_criar, name="receita_criar"),
    path("receitas/<int:pk>/editar/", views.receita_editar, name="receita_editar"),
    path("receitas/<int:pk>/receber/", views.receita_marcar_recebida, name="receita_marcar_recebida"),
    path("despesas/", views.despesa_lista, name="despesa_lista"),
    path("despesas/nova/", views.despesa_criar, name="despesa_criar"),
    path("despesas/<int:pk>/editar/", views.despesa_editar, name="despesa_editar"),
    path("despesas/<int:pk>/pagar/", views.despesa_marcar_paga, name="despesa_marcar_paga"),
    path("despesas/<int:pk>/cancelar/", views.despesa_cancelar, name="despesa_cancelar"),
    path("exportar/", views.exportar_csv, name="exportar_csv"),
    path("controle/", views.controle, name="controle"),
    path("controle/reservas/nova/", views.reserva_criar, name="reserva_criar"),
    path("controle/reservas/<int:pk>/editar/", views.reserva_editar, name="reserva_editar"),
]
