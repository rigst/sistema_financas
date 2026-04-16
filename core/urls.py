from django.urls import path
from .views import alternar_empresa, dashboard, healthz, manual

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("", dashboard, name="dashboard"),
    path("manual/", manual, name="manual"),
    path("empresa/alternar/", alternar_empresa, name="alternar_empresa"),
]
