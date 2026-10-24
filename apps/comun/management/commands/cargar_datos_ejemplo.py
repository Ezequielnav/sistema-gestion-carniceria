from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.comun.datos_ejemplo import cargar


class Command(BaseCommand):
    help = "Carga datos ficticios de ejemplo (H1.3). Solo para desarrollo local."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Los datos de ejemplo solo se cargan en desarrollo local (DJANGO_DEBUG=True)."
            )
        if not settings.DEMO_PASSWORD:
            raise CommandError("Falta DEMO_PASSWORD en el .env (ver README).")
        creados = cargar(settings.DEMO_PASSWORD)
        for tipo, cantidad in creados.items():
            self.stdout.write(f"{tipo}: {cantidad} nuevos")
        self.stdout.write(self.style.SUCCESS("Datos de ejemplo cargados."))
