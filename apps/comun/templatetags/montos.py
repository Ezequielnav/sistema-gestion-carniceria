"""Montos en pesos para las pantallas, con el signo adelante si son negativos (RM-13)."""

from django import template

from apps.comun.models import pesos

register = template.Library()


@register.filter
def monto(valor):
    """$ 1.234,56; un negativo, −$ 100,00 (antes se veía "$ -100,00")."""
    if valor is None or valor == "":
        return ""
    return f"−{pesos(-valor)}" if valor < 0 else pesos(valor)
