from django.contrib import admin

from apps.catalogo.models import AjusteStock, Categoria, Producto, formatear_cantidad
from apps.comun.admin import AdminBase, SoloLecturaAdmin


@admin.register(Categoria)
class CategoriaAdmin(AdminBase):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(Producto)
class ProductoAdmin(AdminBase):
    list_display = ("nombre", "plus_interno", "categoria", "precio_venta", "stock_actual", "activo")
    list_filter = ("activo", "controla_stock", "categoria")
    search_fields = ("nombre", "plus_interno")
    # El stock lo cambian solo ventas, ingresos y ajustes con registro (RI-07, DEC-100).
    readonly_fields = ("stock_actual",)

    def has_add_permission(self, request):
        # El alta va por /productos/: RN-05 y el stock inicial como ajuste (DEC-99, DEC-100).
        return False


@admin.register(AjusteStock)
class AjusteStockAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "producto", "anterior", "nuevo", "motivo", "usuario")
    list_filter = ("motivo",)
    search_fields = ("producto__nombre",)
    fields = ("fecha_hora", "producto", "usuario", "anterior", "nuevo", "motivo", "observacion")
    readonly_fields = ("anterior", "nuevo")

    # DEC-48: "2" por unidad y "1,250 kg" por kg, como en el resto del sistema.
    @admin.display(description="Stock anterior")
    def anterior(self, obj):
        return formatear_cantidad(obj.stock_anterior, obj.producto.unidad_medida)

    @admin.display(description="Stock nuevo")
    def nuevo(self, obj):
        return formatear_cantidad(obj.stock_nuevo, obj.producto.unidad_medida)
