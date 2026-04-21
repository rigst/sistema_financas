from django.urls import path
from .views import dashboard, gerar_mentoria_ia, healthz, manual

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("", dashboard, name="dashboard"),
    path("mentoria-ia/gerar/", gerar_mentoria_ia, name="gerar_mentoria_ia"),
    path("manual/", manual, name="manual"),
]
