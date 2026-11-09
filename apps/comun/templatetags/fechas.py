"""Fechas con el día de la semana abreviado y con tilde (H7): "Mié 4/11/2026", "Sáb 7/11".

El formato "D" de Django en español abrevia sin tilde ("Mie", "Sab"); este filtro se usa en
la pantalla y en el PDF de los reportes para que coincidan.
"""

from django import template
from django.utils.formats import date_format

register = template.Library()

DIAS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


@register.filter
def con_dia(fecha, formato="j/m/Y"):
    """El día de la semana abreviado, con tilde, seguido de la fecha en `formato`."""
    if not fecha:
        return ""
    return f"{DIAS[fecha.weekday()]} {date_format(fecha, formato)}"
