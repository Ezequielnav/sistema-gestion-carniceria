from django.contrib import admin
from django.contrib.admin.utils import display_for_value

from apps.comun.admin import RenglonesSoloLecturaInline, SoloLecturaAdmin
from apps.ventas.models import DetalleVenta, EstadoVenta, Venta


class DetalleVentaInline(RenglonesSoloLecturaInline):
    model = DetalleVenta
    fields = ("producto", "cantidad_con_unidad", "precio_unitario", "subtotal")
    readonly_fields = fields
    verbose_name = "producto"
    verbose_name_plural = "productos de la venta"


@admin.register(Venta)
class VentaAdmin(SoloLecturaAdmin):
    list_display = ("id", "fecha_hora_venta", "caja", "medio_de_pago", "cliente", "monto_total")
    inlines = (DetalleVentaInline,)
    readonly_fields = (
        "fecha_hora_venta",
        "medio_de_pago",
        "fecha_hora_anulacion",
        "anulada_por",
        "motivo",
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (
                "Venta",
                {
                    "fields": (
                        "fecha_hora_venta",
                        "caja",
                        "usuario",
                        "cliente",
                        "medio_de_pago",
                        "monto_total",
                        "estado",
                    )
                },
            )
        ]
        # Los datos de la anulación existen solo si la venta está anulada (DEC-67).
        if obj is not None and obj.estado == EstadoVenta.ANULADA:
            fieldsets.append(
                ("Anulación", {"fields": ("fecha_hora_anulacion", "anulada_por", "motivo")})
            )
        return fieldsets

    @admin.display(description="Fecha y hora de la venta", ordering="fecha_hora")
    def fecha_hora_venta(self, obj):
        # Los campos calculados de solo lectura no se formatean solos: hora local y formato es-AR.
        return display_for_value(obj.fecha_hora, self.get_empty_value_display())

    @admin.display(description="Medio de pago", ordering="medio_pago")
    def medio_de_pago(self, obj):
        return obj.medio_pago

    @admin.display(description="Fecha y hora de anulación")
    def fecha_hora_anulacion(self, obj):
        return display_for_value(obj.anulada_en, self.get_empty_value_display())

    @admin.display(description="Anulada por")
    def anulada_por(self, obj):
        return obj.anulada_por_usuario

    @admin.display(description="Motivo de anulación")
    def motivo(self, obj):
        return obj.motivo_anulacion
