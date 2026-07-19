from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView
from usuarios.views import UsuarioLoginView, UsuarioLogoutView

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "favicon.ico", permanent=True)),
    path("admin/", admin.site.urls),
    # Páginas legais (LGPD): acessíveis sem login.
    path("privacidade/", TemplateView.as_view(template_name="legal/privacidade.html"), name="privacidade"),
    path("termos/", TemplateView.as_view(template_name="legal/termos.html"), name="termos"),
    path("login/", UsuarioLoginView.as_view(), name="login"),
    path("logout/", UsuarioLogoutView.as_view(), name="logout"),
    path("", include("core.urls")),
    path("financeiro/", include("financeiro.urls")),
]

if settings.DEBUG and settings.DEBUG_EXPOSE_MEDIA:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
