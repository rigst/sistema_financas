from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ItemOrcamento


@receiver(post_save, sender=ItemOrcamento)
def recalcular_orcamento_apos_salvar_item(sender, instance, **kwargs):
    instance.orcamento.recalcular_totais()


@receiver(post_delete, sender=ItemOrcamento)
def recalcular_orcamento_apos_excluir_item(sender, instance, **kwargs):
    instance.orcamento.recalcular_totais()
