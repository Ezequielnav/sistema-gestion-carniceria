from django.contrib import admin

from apps.catalogo.models import Categoria, Producto
from apps.comun.admin import AdminBase


@admin.register(Categoria)
class CategoriaAdmin(AdminBase):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(Producto)
class ProductoAdmin(AdminBase):
    list_display = ("nombre", "plus_interno", "categoria", "precio_venta", "stock_actual", "activo")
    list_filter = ("activo", "controla_stock", "categoria")
    search_fields = ("nombre", "plus_interno")
    # El stock lo cambian solo las ventas y los ingresos (RI-07).
    readonly_fields = ("stock_actual",)
