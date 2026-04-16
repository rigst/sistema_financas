from django.core.management.base import BaseCommand

from usuarios.visitantes import limpar_visitantes_expirados


class Command(BaseCommand):
    help = "Remove usuários visitantes expirados e seus dados relacionados."

    def handle(self, *args, **options):
        limpar_visitantes_expirados()
        self.stdout.write(self.style.SUCCESS("Limpeza de visitantes expirados concluída."))
