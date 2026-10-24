from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.comun.models import NO_NEGATIVO, ModeloBase, campo_cantidad, campo_monto, validar_positivo


class Venta(ModeloBase):
    fecha_hora = models.DateTimeField(default=timezone.now)
    caja = models.ForeignKey("caja.Caja", on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    # Obligatorio si el medio de pago es cuenta corriente (a confirmar: PR-12).
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT, null=True, blank=True)
    # Un solo medio por venta (pago mixto a confirmar: PR-09).
    medio_pago = models.ForeignKey("caja.MedioPago", on_delete=models.PROTECT)
    # Suma de los subtotales de sus detalles (RI-03).
    monto_total = campo_monto(validators=[NO_NEGATIVO])

    class Meta:
        db_table = "venta"
        constraints = [
            models.CheckConstraint(
                condition=Q(monto_total__gte=0), name="venta_monto_total_no_negativo"
            ),
        ]
        indexes = [
            models.Index(fields=["caja", "fecha_hora"], name="venta_caja_fecha_idx"),
        ]

    def __str__(self):
        return f"Venta {self.pk}"


class DetalleVenta(ModeloBase):
    venta = models.ForeignKey(Venta, on_delete=models.PROTECT)
    producto = models.ForeignKey("catalogo.Producto", on_delete=models.PROTECT)
    cantidad = campo_cantidad(validators=[validar_positivo])
    # Precio al momento de la venta (RI-12).
    precio_unitario = campo_monto(validators=[NO_NEGATIVO])
    subtotal = campo_monto(validators=[NO_NEGATIVO])

    class Meta:
        db_table = "detalle_venta"
        verbose_name = "detalle de venta"
        verbose_name_plural = "detalles de venta"
        constraints = [
            models.CheckConstraint(
                condition=Q(cantidad__gt=0), name="detalle_venta_cantidad_positiva"
            ),
            models.CheckConstraint(
                condition=Q(precio_unitario__gte=0), name="detalle_venta_precio_no_negativo"
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0), name="detalle_venta_subtotal_no_negativo"
            ),
        ]

    def __str__(self):
        return f"{self.producto} x {self.cantidad}"
