from django.contrib import admin

from apps.clientes.models import Cliente, MovimientoCuentaCorriente, PagoCliente
from apps.comun.admin import AdminBase, SoloLecturaAdmin


@admin.register(Cliente)
class ClienteAdmin(AdminBase):
    list_display = ("nombre", "telefono", "limite_credito", "activo")
    search_fields = ("nombre",)


@admin.register(PagoCliente)
class PagoClienteAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "cliente", "monto", "medio_pago")


@admin.register(MovimientoCuentaCorriente)
class MovimientoCuentaCorrienteAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "cliente", "tipo", "monto", "fecha_vencimiento")
    list_filter = ("tipo",)
