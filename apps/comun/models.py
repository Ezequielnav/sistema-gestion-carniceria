from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class ModeloBase(models.Model):
    """Auditoría común a todas las tablas (05, sección 1)."""

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# Repiten en los formularios los CHECK de la base (RI-16), para que el error se muestre junto al
# campo con un mensaje claro en lugar del nombre de la restricción.
NO_NEGATIVO = MinValueValidator(Decimal("0"), message="No puede ser negativo.")


def validar_positivo(valor):
    if valor is not None and valor <= 0:
        raise ValidationError("Debe ser mayor a 0.", code="positivo")


def campo_monto(**kwargs):
    """Montos en pesos con dos decimales (DEC-22)."""
    return models.DecimalField(max_digits=12, decimal_places=2, **kwargs)


def campo_cantidad(**kwargs):
    """Cantidades y stock con tres decimales, para productos por kg (PR-03)."""
    return models.DecimalField(max_digits=12, decimal_places=3, **kwargs)
