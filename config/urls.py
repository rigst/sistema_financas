from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from usuarios.views import UsuarioLoginView, UsuarioLogoutView

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "favicon.ico", permanent=True)),
    path("admin/", admin.site.urls),
    path("login/", UsuarioLoginView.as_view(), name="login"),
    path("logout/", UsuarioLogoutView.as_view(), name="logout"),
    path("", include("core.urls")),
    path("clientes/", include("clientes.urls")),
    path("catalogo/", include("catalogo.urls")),
    path("relatorios/", include("relatorios.urls")),
    path("orcamentos/", include("orcamentos.urls")),
]

if settings.DEBUG and settings.DEBUG_EXPOSE_MEDIA:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
