import os
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from financeiro.models import Despesa, Receita, Reserva

logger = logging.getLogger(__name__)


def _visitante_rate_limit() -> int:
    return max(int(os.getenv("DJANGO_VISITANTE_RATE_LIMIT", "20")), 1)


def _visitante_rate_window_seconds() -> int:
    return max(int(os.getenv("DJANGO_VISITANTE_RATE_WINDOW_SECONDS", "300")), 30)


def _visitante_ttl_hours() -> int:
    return max(int(os.getenv("DJANGO_VISITANTE_TTL_HOURS", "24")), 1)


def _rate_limit_key(ip: str) -> str:
    return f"visitante:rate:{ip or 'desconhecido'}"


def excedeu_rate_limit_visitante(ip: str) -> bool:
    chave = _rate_limit_key(ip)
    tentativas = cache.get(chave, 0)
    return int(tentativas) >= _visitante_rate_limit()


def registrar_tentativa_visitante(ip: str):
    chave = _rate_limit_key(ip)
    janela = _visitante_rate_window_seconds()
    if cache.add(chave, 1, timeout=janela):
        return
    try:
        cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, timeout=janela)


def limpar_dados_visitante(user):
    if not user or not getattr(user, "username", "").startswith("visitante_"):
        return

    Despesa.objects.filter(criado_por=user).delete()
    Receita.objects.filter(criado_por=user).delete()
    Reserva.objects.filter(criado_por=user).delete()
    user.delete()


def limpar_visitantes_expirados():
    limite = timezone.now() - timedelta(hours=_visitante_ttl_hours())
    usuarios_expirados = (
        get_user_model()
        .objects.filter(username__startswith="visitante_", criado_em__lt=limite)
        .order_by("criado_em")
        .iterator()
    )
    total = 0
    for visitante in usuarios_expirados:
        limpar_dados_visitante(visitante)
        total += 1
    if total:
        logger.info("Visitantes expirados removidos", extra={"total": total})
