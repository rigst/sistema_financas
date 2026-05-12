from .models import ParticipanteCompartilhamentoDespesa


def compartilhamentos_pendentes(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"compartilhamentos_pendentes_count": 0}
    pendentes_recebidos = ParticipanteCompartilhamentoDespesa.objects.filter(
        usuario=request.user,
        status="pendente",
    ).count()
    recusas_recebidas = ParticipanteCompartilhamentoDespesa.objects.filter(
        compartilhamento__criado_por=request.user,
        status="recusado",
    ).count()
    aguardando_criador = ParticipanteCompartilhamentoDespesa.objects.filter(
        compartilhamento__criado_por=request.user,
        status="pendente",
    ).count()
    recusas_notificadas = ParticipanteCompartilhamentoDespesa.objects.filter(
        usuario=request.user,
        status="recusado",
    ).exclude(compartilhamento__recusado_por=request.user).count()
    return {
        "compartilhamentos_pendentes_count": pendentes_recebidos + recusas_recebidas + recusas_notificadas + aguardando_criador
    }
