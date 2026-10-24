from django.contrib import admin

from apps.comun.admin import AdminBase, SoloLecturaAdmin
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


@admin.register(IngresoMercaderia)
class IngresoMercaderiaAdmin(SoloLecturaAdmin):
    list_display = ("id", "fecha", "proveedor", "total", "condicion_pago")


@admin.register(DetalleIngreso)
class DetalleIngresoAdmin(SoloLecturaAdmin):
    list_display = ("ingreso", "producto", "cantidad", "precio_unitario", "fecha_vencimiento")


@admin.register(PagoProveedor)
class PagoProveedorAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "proveedor", "ingreso", "monto", "medio_pago")
