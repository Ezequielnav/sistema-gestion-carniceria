from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from unfold.admin import ModelAdmin

from apps.comun.models import validar_positivo


class AdminBase(ModelAdmin):
    """Agrega el mínimo del navegador a los montos y cantidades que no admiten negativos."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        campo = super().formfield_for_dbfield(db_field, request, **kwargs)
        if campo is not None and isinstance(db_field, models.DecimalField):
            if validar_positivo in db_field.validators:
                # El navegador no admite un mínimo excluido: se usa el menor valor positivo.
                campo.widget.attrs["min"] = str(Decimal(1).scaleb(-db_field.decimal_places))
            elif any(isinstance(v, MinValueValidator) for v in db_field.validators):
                campo.widget.attrs["min"] = "0"
        return campo


class SoloLecturaAdmin(AdminBase):
    """Registros operativos (ventas, cajas, pagos, ingresos y sus movimientos).

    Solo se crean desde su caso de uso, que aplica las reglas de negocio en una transacción
    (RI-02 a RI-08, RNF-10). En el panel se consultan, sin alta, cambios ni borrado (DEC-31).
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
