"""Sonda de saúde do smoke-test do CD (rigst/ci RUNBOOK.md, seção 7.8).

Responde 200 só quando o processo consegue usar o que precisa para servir uma
página: banco e cache. Qualquer falha vira 503, que o deploy/cd-deploy.sh
trata como deploy quebrado e reverte. Este app não usa Celery, então não há
broker a checar.

O token continua valendo: com DJANGO_HEALTHZ_TOKEN definido, sem o cabeçalho
X-Healthz-Token correto a rota responde 404, como se não existisse. O corpo
mantém o formato JSON de antes (`{"status": "ok"}`), só ganhou o estado
`indisponivel`; qual componente caiu fica no log, não na resposta.

A rota fica livre do aceite de termos (`/healthz` em
legal.middleware.PREFIXOS_LIVRES) e não exige login.
"""

import logging
import secrets
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)


def _banco():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _cache():
    chave = f"healthz:{uuid.uuid4().hex}"
    cache.set(chave, "1", 10)
    if cache.get(chave) != "1":
        raise RuntimeError("cache não devolveu o valor gravado")
    cache.delete(chave)


VERIFICACOES = (("banco", _banco), ("cache", _cache))


def _token_valido(request):
    healthz_token = getattr(settings, "HEALTHZ_TOKEN", "")
    if not healthz_token:
        return True
    token_recebido = request.headers.get("X-Healthz-Token", "").strip()
    return bool(token_recebido) and secrets.compare_digest(token_recebido, healthz_token)


@never_cache
@require_safe
def healthz(request):
    if not _token_valido(request):
        return HttpResponseNotFound()
    falhas = []
    for nome, verificar in VERIFICACOES:
        try:
            verificar()
        except Exception:  # sonda: qualquer falha é "indisponível", e vai para o log
            logger.exception("healthz: %s indisponível", nome)
            falhas.append(nome)
    if falhas:
        return JsonResponse({"status": "indisponivel"}, status=503)
    return JsonResponse({"status": "ok"})
