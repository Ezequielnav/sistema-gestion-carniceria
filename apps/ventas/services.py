from decimal import Decimal

from django.db.models import Count, Sum

from apps.ventas.models import Venta


def resumen_del_dia(fecha):
    """Cantidad y monto total de las ventas de una fecha (hora local)."""
    datos = Venta.objects.filter(fecha_hora__date=fecha).aggregate(
        cantidad=Count("id"), total=Sum("monto_total")
    )
    return datos["cantidad"], datos["total"] or Decimal("0.00")


def ultimas_ventas(limite=5):
    return list(
        Venta.objects.select_related("medio_pago", "cliente").order_by("-fecha_hora")[:limite]
    )
