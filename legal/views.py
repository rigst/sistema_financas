"""Páginas públicas dos documentos legais e o interstitial de re-aceite."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import AceiteForm
from .models import AceiteLegal, DocumentoLegal, OrigemAceite, StatusDocumento, TipoDocumento
from .services import documentos_pendentes, historico, registrar_aceite


def _documento_vigente_ou_404(tipo):
    documento = DocumentoLegal.objects.vigente(tipo)
    if documento is None:
        raise Http404("Nenhuma versão publicada deste documento.")
    return documento


def _pagina_documento(request, tipo):
    documento = _documento_vigente_ou_404(tipo)
    return render(
        request,
        "legal/documento.html",
        {
            "documento": documento,
            "versoes": historico(tipo),
            "e_versao_vigente": True,
        },
    )


def termos(request):
    return _pagina_documento(request, TipoDocumento.TERMOS)


def privacidade(request):
    return _pagina_documento(request, TipoDocumento.PRIVACIDADE)


def versao(request, tipo, versao):
    """Versão específica, inclusive arquivada — transparência sobre o histórico."""
    if tipo not in TipoDocumento.values:
        raise Http404("Tipo de documento desconhecido.")
    documento = get_object_or_404(
        DocumentoLegal,
        tipo=tipo,
        versao=versao,
        status__in=[StatusDocumento.PUBLICADO, StatusDocumento.ARQUIVADO],
    )
    return render(
        request,
        "legal/documento.html",
        {
            "documento": documento,
            "versoes": historico(tipo),
            "e_versao_vigente": documento.status == StatusDocumento.PUBLICADO,
        },
    )


@login_required
def reaceite(request):
    """Bloqueia o uso do sistema até a nova versão ser aceita."""
    pendentes = documentos_pendentes(request.user)
    if not pendentes:
        return redirect(reverse("dashboard"))

    if request.method == "POST":
        form = AceiteForm(request.POST)
        if form.is_valid():
            registrar_aceite(
                request,
                usuario=request.user,
                origem=OrigemAceite.REACEITE,
                documentos=pendentes,
                e_visitante=request.user.username.startswith("visitante_"),
            )
            messages.success(request, "Obrigado. Aceite registrado.")
            return redirect(reverse("dashboard"))
    else:
        form = AceiteForm()

    return render(
        request,
        "legal/reaceite.html",
        {"form": form, "documentos": pendentes},
    )


@login_required
def meus_aceites(request):
    """Comprovante do próprio usuário — LGPD art. 18, direito de acesso."""
    aceites = (
        AceiteLegal.objects.filter(usuario=request.user)
        .select_related("documento")
        .order_by("-aceito_em")
    )
    return render(request, "legal/meus_aceites.html", {"aceites": aceites})
