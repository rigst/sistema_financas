from django.urls import path
from .views import cliente_criar, cliente_editar, cliente_excluir, cliente_lista, cliente_visualizar

app_name = "clientes"

urlpatterns = [
    path("", cliente_lista, name="lista"),
    path("novo/", cliente_criar, name="criar"),
    path("<int:pk>/", cliente_visualizar, name="visualizar"),
    path("<int:pk>/editar/", cliente_editar, name="editar"),
    path("<int:pk>/excluir/", cliente_excluir, name="excluir"),
]
