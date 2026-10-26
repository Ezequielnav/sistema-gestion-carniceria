from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.comun.models import NO_NEGATIVO, ModeloBase, campo_cantidad, campo_monto, validar_positivo


class EstadoVenta(models.TextChoices):
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    ANULADA = "ANULADA", "Anulada"


class Venta(ModeloBase):
    fecha_hora = models.DateTimeField(default=timezone.now)
    caja = models.ForeignKey("caja.Caja", on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    # Obligatorio si el medio de pago es cuenta corriente (a confirmar: PR-12).
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT, null=True, blank=True)
    # Un solo medio por venta (DEC-42).
    medio_pago = models.ForeignKey("caja.MedioPago", on_delete=models.PROTECT)
    # Suma de los subtotales de sus detalles (RI-03).
    monto_total = campo_monto(validators=[NO_NEGATIVO])
    # Una venta no se edita: el Administrador la anula con reversa (DEC-45, DEC-67).
    estado = models.CharField(
        max_length=10, choices=EstadoVenta.choices, default=EstadoVenta.CONFIRMADA
    )
    anulada_en = models.DateTimeField(null=True, blank=True)
    anulada_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ventas_anuladas",
    )
    motivo_anulacion = models.TextField(blank=True)

    class Meta:
        db_table = "venta"
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=EstadoVenta.values), name="venta_estado_valido"
            ),
            # Los datos de la anulación están si y solo si la venta está anulada (DEC-67).
            models.CheckConstraint(
                condition=(
                    Q(
                        estado=EstadoVenta.ANULADA,
                        anulada_en__isnull=False,
                        anulada_por_usuario__isnull=False,
                    )
                    & ~Q(motivo_anulacion="")
                )
                | Q(
                    estado=EstadoVenta.CONFIRMADA,
                    anulada_en__isnull=True,
                    anulada_por_usuario__isnull=True,
                    motivo_anulacion="",
                ),
                name="venta_datos_de_anulacion_segun_estado",
            ),
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
