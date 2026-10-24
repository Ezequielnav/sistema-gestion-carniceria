from django.contrib import admin

from apps.comun.admin import SoloLecturaAdmin
from apps.ventas.models import DetalleVenta, Venta


@admin.register(Venta)
class VentaAdmin(SoloLecturaAdmin):
    list_display = ("id", "fecha_hora", "caja", "medio_pago", "cliente", "monto_total")


@admin.register(DetalleVenta)
class DetalleVentaAdmin(SoloLecturaAdmin):
    list_display = ("venta", "producto", "cantidad", "precio_unitario", "subtotal")
