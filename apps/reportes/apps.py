from django.apps import AppConfig


class ReportesConfig(AppConfig):
    """CU-09: solo lee ventas, caja, clientes y catálogo; nadie la importa (R-1, DEC-154)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reportes"
    verbose_name = "Reportes"
