from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.comun.models import NO_NEGATIVO, ModeloBase, campo_monto, validar_positivo


class TipoMovimientoCuentaCorriente(models.TextChoices):
    """Cargos y abonos de la cuenta corriente. No hay saldo a favor (DEC-111)."""

    VENTA_FIADA = "VENTA_FIADA", "Venta a cuenta corriente"
    PAGO = "PAGO", "Cobro"
    # Movimientos inversos de una anulación (DEC-113).
    ANULACION_VENTA = "ANULACION_VENTA", "Anulación de venta"
    ANULACION_PAGO = "ANULACION_PAGO", "Anulación de cobro"
    # Deuda que el cliente ya tenía al empezar a usar el sistema (DEC-119).
    SALDO_INICIAL = "SALDO_INICIAL", "Saldo inicial"
    ANULACION_SALDO_INICIAL = "ANULACION_SALDO_INICIAL", "Anulación de saldo inicial"


# Suman al saldo; los demás tipos lo restan (DEC-21).
TIPOS_QUE_SUMAN = [
    TipoMovimientoCuentaCorriente.VENTA_FIADA,
    TipoMovimientoCuentaCorriente.ANULACION_PAGO,
    TipoMovimientoCuentaCorriente.SALDO_INICIAL,
]


class EstadoPagoCliente(models.TextChoices):
    VIGENTE = "VIGENTE", "Vigente"
    ANULADO = "ANULADO", "Anulado"


class Cliente(ModeloBase):
    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=30, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    # Vacío = sin límite; 0 = sin crédito habilitado (DEC-108, DEC-115).
    limite_credito = campo_monto(null=True, blank=True, validators=[NO_NEGATIVO])
    # Notas y condiciones de crédito, sin efecto en el saldo (DEC-112, DEC-117).
    observaciones = models.TextField(blank=True)
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
    # Si generó el ingreso PAGO_CLIENTE en la caja abierta (DEC-110).
    entra_a_caja = models.BooleanField(default=False)
    estado = models.CharField(
        max_length=7, choices=EstadoPagoCliente.choices, default=EstadoPagoCliente.VIGENTE
    )
    anulado_en = models.DateTimeField(null=True, blank=True)
    anulado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagos_cliente_anulados",
    )
    motivo_anulacion = models.TextField(blank=True)

    class Meta:
        db_table = "pago_cliente"
        verbose_name = "pago de cliente"
        verbose_name_plural = "pagos de clientes"
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name="pago_cliente_monto_positivo"),
            models.CheckConstraint(
                condition=Q(estado__in=EstadoPagoCliente.values), name="pago_cliente_estado_valido"
            ),
            # Los datos de la anulación están si y solo si el cobro está anulado (DEC-113).
            models.CheckConstraint(
                condition=(
                    Q(
                        estado=EstadoPagoCliente.ANULADO,
                        anulado_en__isnull=False,
                        anulado_por_usuario__isnull=False,
                    )
                    & ~Q(motivo_anulacion="")
                )
                | Q(
                    estado=EstadoPagoCliente.VIGENTE,
                    anulado_en__isnull=True,
                    anulado_por_usuario__isnull=True,
                    motivo_anulacion="",
                ),
                name="pago_cliente_datos_de_anulacion_segun_estado",
            ),
        ]

    def __str__(self):
        return f"Pago {self.pk} - {self.cliente}"


def _referencias(venta=False, pago_cliente=False, saldo_inicial=False):
    return Q(
        venta__isnull=not venta,
        pago_cliente__isnull=not pago_cliente,
        saldo_inicial__isnull=not saldo_inicial,
    )


class MovimientoCuentaCorriente(ModeloBase):
    """Libro de la cuenta corriente. El monto es siempre positivo; el efecto lo da el tipo."""

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    fecha_hora = models.DateTimeField(default=timezone.now)
    tipo = models.CharField(max_length=23, choices=TipoMovimientoCuentaCorriente.choices)
    monto = campo_monto(validators=[validar_positivo])
    venta = models.ForeignKey("ventas.Venta", on_delete=models.PROTECT, null=True, blank=True)
    pago_cliente = models.ForeignKey(PagoCliente, on_delete=models.PROTECT, null=True, blank=True)
    # El saldo inicial que anula una ANULACION_SALDO_INICIAL (DEC-119).
    saldo_inicial = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="anulaciones"
    )
    # Fecha de la deuda de un saldo inicial; es la que cuenta para el vencimiento (DEC-119).
    fecha_origen = models.DateField(null=True, blank=True)
    motivo = models.CharField(max_length=255, blank=True)

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
            # La venta y su anulación llevan la venta; el cobro y su anulación, el cobro; el
            # saldo inicial no lleva nada y su anulación, el saldo inicial (DEC-113, DEC-119).
            # RI-15 (mismo cliente que el origen) se valida en el servicio.
            models.CheckConstraint(
                condition=(
                    Q(
                        tipo__in=[
                            TipoMovimientoCuentaCorriente.VENTA_FIADA,
                            TipoMovimientoCuentaCorriente.ANULACION_VENTA,
                        ]
                    )
                    & _referencias(venta=True)
                    | Q(
                        tipo__in=[
                            TipoMovimientoCuentaCorriente.PAGO,
                            TipoMovimientoCuentaCorriente.ANULACION_PAGO,
                        ]
                    )
                    & _referencias(pago_cliente=True)
                    | Q(tipo=TipoMovimientoCuentaCorriente.SALDO_INICIAL) & _referencias()
                    | Q(tipo=TipoMovimientoCuentaCorriente.ANULACION_SALDO_INICIAL)
                    & _referencias(saldo_inicial=True)
                ),
                name="movimiento_cuenta_corriente_referencia_segun_tipo",
            ),
            # Solo el saldo inicial tiene fecha de origen, y él y su anulación llevan motivo.
            models.CheckConstraint(
                condition=(
                    Q(tipo=TipoMovimientoCuentaCorriente.SALDO_INICIAL, fecha_origen__isnull=False)
                    & ~Q(motivo="")
                    | Q(tipo=TipoMovimientoCuentaCorriente.ANULACION_SALDO_INICIAL)
                    & Q(fecha_origen__isnull=True)
                    & ~Q(motivo="")
                    | ~Q(
                        tipo__in=[
                            TipoMovimientoCuentaCorriente.SALDO_INICIAL,
                            TipoMovimientoCuentaCorriente.ANULACION_SALDO_INICIAL,
                        ]
                    )
                    & Q(fecha_origen__isnull=True, motivo="")
                ),
                name="movimiento_cuenta_corriente_datos_de_saldo_inicial",
            ),
            # Una venta tiene su cargo y a lo sumo una anulación; un cobro, su abono y a lo
            # sumo una anulación; un saldo inicial, a lo sumo una anulación (DEC-113, RI-18).
            models.UniqueConstraint(
                fields=["venta", "tipo"],
                condition=Q(venta__isnull=False),
                name="movimiento_cuenta_corriente_venta_y_tipo_unicos",
            ),
            models.UniqueConstraint(
                fields=["pago_cliente", "tipo"],
                condition=Q(pago_cliente__isnull=False),
                name="movimiento_cuenta_corriente_pago_y_tipo_unicos",
            ),
            models.UniqueConstraint(
                fields=["saldo_inicial"],
                condition=Q(saldo_inicial__isnull=False),
                name="movimiento_cuenta_corriente_una_anulacion_por_saldo_inicial",
            ),
        ]
        indexes = [
            models.Index(fields=["cliente", "fecha_hora"], name="mov_cc_cliente_fecha_idx"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.monto} - {self.cliente}"
