from django import template

from apps.catalogo.models import formatear_cantidad

register = template.Library()


@register.filter
def cantidad(valor, unidad):
    """{{ detalle.cantidad|cantidad:detalle.producto.unidad_medida }} (ver formatear_cantidad)."""
    return formatear_cantidad(valor, unidad)
