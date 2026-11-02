from django.contrib import admin

from apps.caja.models import Caja, CierreCajaDetalle, MedioPago, MovimientoCaja
from apps.comun.admin import AdminBase, SoloLecturaAdmin


@admin.register(MedioPago)
class MedioPagoAdmin(AdminBase):
    list_display = ("nombre", "ingresa_a_caja", "es_efectivo", "activo")


@admin.register(Caja)
class CajaAdmin(SoloLecturaAdmin):
    list_display = ("fecha", "turno", "estado", "usuario", "abierta_en", "cerrada_en")
    list_filter = ("estado", "turno")


@admin.register(CierreCajaDetalle)
class CierreCajaDetalleAdmin(SoloLecturaAdmin):
    list_display = ("caja", "medio_pago", "monto_sistema", "monto_contado")


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "caja", "tipo", "concepto", "monto", "medio_pago")
    list_filter = ("tipo", "concepto")
