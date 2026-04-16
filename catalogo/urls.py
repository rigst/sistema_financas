from django.urls import path

from .views import (
    categoria_criar,
    categoria_editar,
    categoria_excluir,
    categoria_lista,
    categoria_visualizar,
    item_criar,
    item_editar,
    item_excluir,
    catalogo_importar_excel,
    item_exportar_excel,
    item_lista,
    item_visualizar,
)

app_name = "catalogo"

urlpatterns = [
    path("categorias/", categoria_lista, name="categoria_lista"),
    path("categorias/nova/", categoria_criar, name="categoria_criar"),
    path("categorias/<int:pk>/", categoria_visualizar, name="categoria_visualizar"),
    path("categorias/<int:pk>/editar/", categoria_editar, name="categoria_editar"),
    path("categorias/<int:pk>/excluir/", categoria_excluir, name="categoria_excluir"),
    path("itens/", item_lista, name="item_lista"),
    path("itens/novo/", item_criar, name="item_criar"),
    path("itens/importar/", catalogo_importar_excel, name="item_importar_excel"),
    path("itens/exportar/", item_exportar_excel, name="item_exportar_excel"),
    path("itens/<int:pk>/", item_visualizar, name="item_visualizar"),
    path("itens/<int:pk>/editar/", item_editar, name="item_editar"),
    path("itens/<int:pk>/excluir/", item_excluir, name="item_excluir"),
]
