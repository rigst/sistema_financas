from django.urls import path

from .healthz import healthz
from .views import dashboard, gerar_mentoria_ia

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("", dashboard, name="dashboard"),
    path("mentoria-ia/gerar/", gerar_mentoria_ia, name="gerar_mentoria_ia"),
]
