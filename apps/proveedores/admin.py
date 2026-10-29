from django.contrib import admin

from apps.comun.admin import AdminBase, RenglonesSoloLecturaInline, SoloLecturaAdmin
from apps.proveedores.models import (
    DetalleIngreso,
    IngresoMercaderia,
    PagoProveedor,
    ProductoProveedor,
    Proveedor,
)


@admin.register(Proveedor)
class ProveedorAdmin(AdminBase):
    list_display = ("nombre", "telefono", "email", "activo")
    search_fields = ("nombre",)


@admin.register(ProductoProveedor)
class ProductoProveedorAdmin(AdminBase):
    list_display = ("producto", "proveedor", "precio_compra")


class DetalleIngresoInline(RenglonesSoloLecturaInline):
    model = DetalleIngreso
    fields = ("producto", "cantidad", "precio_unitario", "fecha_vencimiento")
    verbose_name = "producto"
    verbose_name_plural = "productos del ingreso"


@admin.register(IngresoMercaderia)
class IngresoMercaderiaAdmin(SoloLecturaAdmin):
    list_display = ("id", "fecha", "proveedor", "total", "condicion_pago")
    inlines = (DetalleIngresoInline,)


@admin.register(PagoProveedor)
class PagoProveedorAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "proveedor", "ingreso", "monto", "medio_pago")
