from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.comun.models import NO_NEGATIVO, ModeloBase, campo_monto, validar_positivo


class TipoMovimientoCuentaCorriente(models.TextChoices):
    VENTA_FIADA = "VENTA_FIADA", "Venta fiada"
    PAGO = "PAGO", "Pago"
    # Saldo a favor (a confirmar: PR-15).
    ANTICIPO = "ANTICIPO", "Anticipo"


class Cliente(ModeloBase):
    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=30, blank=True)
    # A confirmar (PR-12).
    limite_credito = campo_monto(null=True, blank=True, validators=[NO_NEGATIVO])
    condiciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "cliente"
        constraints = [
            models.CheckConstraint(
                condition=Q(limite_credito__gte=0), name="cliente_limite_credito_no_negativo"
            ),
        ]

    def __str__(self):
        return self.nombre


class PagoCliente(ModeloBase):
    fecha_hora = models.DateTimeField(default=timezone.now)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    monto = campo_monto(validators=[validar_positivo])
    medio_pago = models.ForeignKey("caja.MedioPago", on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        db_table = "pago_cliente"
        verbose_name = "pago de cliente"
        verbose_name_plural = "pagos de clientes"
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name="pago_cliente_monto_positivo"),
        ]

    def __str__(self):
        return f"Pago {self.pk} - {self.cliente}"


class MovimientoCuentaCorriente(ModeloBase):
    """Libro de la cuenta corriente. El monto es siempre positivo; el efecto lo da el tipo."""

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    fecha_hora = models.DateTimeField(default=timezone.now)
    tipo = models.CharField(max_length=11, choices=TipoMovimientoCuentaCorriente.choices)
    monto = campo_monto(validators=[validar_positivo])
    venta = models.ForeignKey("ventas.Venta", on_delete=models.PROTECT, null=True, blank=True)
    pago_cliente = models.ForeignKey(PagoCliente, on_delete=models.PROTECT, null=True, blank=True)
    # Solo para VENTA_FIADA (a confirmar: PR-13).
    fecha_vencimiento = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "movimiento_cuenta_corriente"
        verbose_name = "movimiento de cuenta corriente"
        verbose_name_plural = "movimientos de cuenta corriente"
        constraints = [
            models.CheckConstraint(
                condition=Q(monto__gt=0), name="movimiento_cuenta_corriente_monto_positivo"
            ),
            models.CheckConstraint(
                condition=Q(tipo__in=TipoMovimientoCuentaCorriente.values),
                name="movimiento_cuenta_corriente_tipo_valido",
            ),
            # VENTA_FIADA referencia solo la venta; PAGO y ANTICIPO, solo el pago.
            # RI-15 (mismo cliente que el origen) se valida en el servicio.
            models.CheckConstraint(
                condition=(
                    Q(
                        tipo=TipoMovimientoCuentaCorriente.VENTA_FIADA,
                        venta__isnull=False,
                        pago_cliente__isnull=True,
                    )
                    | Q(
                        tipo__in=[
                            TipoMovimientoCuentaCorriente.PAGO,
                            TipoMovimientoCuentaCorriente.ANTICIPO,
                        ],
                        venta__isnull=True,
                        pago_cliente__isnull=False,
                    )
                ),
                name="movimiento_cuenta_corriente_referencia_segun_tipo",
            ),
            # Una venta genera como mucho un movimiento (05, diagrama 3.1).
            models.UniqueConstraint(
                fields=["venta"],
                condition=Q(venta__isnull=False),
                name="movimiento_cuenta_corriente_venta_unica",
            ),
        ]
        indexes = [
            models.Index(fields=["cliente", "fecha_hora"], name="mov_cc_cliente_fecha_idx"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.monto} - {self.cliente}"
