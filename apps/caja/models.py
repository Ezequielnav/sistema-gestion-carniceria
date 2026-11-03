from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.comun.models import NO_NEGATIVO, ModeloBase, campo_monto, validar_positivo


class Turno(models.TextChoices):
    MANANA = "MANANA", "Mañana"
    TARDE = "TARDE", "Tarde"


class EstadoCaja(models.TextChoices):
    ABIERTA = "ABIERTA", "Abierta"
    CERRADA = "CERRADA", "Cerrada"


class TipoMovimientoCaja(models.TextChoices):
    INGRESO = "INGRESO", "Ingreso"
    EGRESO = "EGRESO", "Egreso"


class ConceptoMovimientoCaja(models.TextChoices):
    """Gastos y retiros (DEC-43) y reversas de anulaciones (DEC-68, DEC-92, DEC-113)."""

    VENTA = "VENTA", "Venta"
    PAGO_CLIENTE = "PAGO_CLIENTE", "Pago de cliente"
    PAGO_PROVEEDOR = "PAGO_PROVEEDOR", "Pago a proveedor"
    OTRO = "OTRO", "Otro"
    # Reversa de una venta anulada (DEC-45, DEC-68).
    ANULACION = "ANULACION", "Anulación de venta"
    # Reversa de un pago a proveedor en efectivo anulado (DEC-92).
    ANULACION_PAGO = "ANULACION_PAGO", "Anulación de pago a proveedor"
    # Reversa de un cobro a cliente anulado que entró a caja (DEC-113).
    ANULACION_COBRO = "ANULACION_COBRO", "Anulación de cobro"


class MedioPago(ModeloBase):
    """Los medios se cargan en el panel (DEC-41, PR-08 cerrada)."""

    nombre = models.CharField(max_length=50)
    ingresa_a_caja = models.BooleanField(default=True)
    # El medio del fondo de cambio y de los egresos "otros" (DEC-55).
    es_efectivo = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "medio_pago"
        verbose_name = "medio de pago"
        verbose_name_plural = "medios de pago"
        constraints = [
            # Sin distinguir mayúsculas: "Efectivo" y "efectivo" son el mismo medio.
            models.UniqueConstraint(
                Lower("nombre"),
                name="medio_pago_nombre_unico",
                violation_error_message="Ya existe un medio de pago con ese nombre.",
            ),
            # DEC-55: un solo medio en efectivo.
            models.UniqueConstraint(
                fields=["es_efectivo"],
                condition=Q(es_efectivo=True),
                name="medio_pago_un_solo_efectivo",
                violation_error_message="Ya hay otro medio de pago marcado como efectivo.",
            ),
            # Cuenta corriente es el único medio que no ingresa a caja (DEC-41, R-6).
            models.UniqueConstraint(
                fields=["ingresa_a_caja"],
                condition=Q(ingresa_a_caja=False),
                name="medio_pago_una_sola_cuenta_corriente",
                violation_error_message="Ya hay otro medio de pago que no ingresa a caja.",
            ),
            models.CheckConstraint(
                condition=Q(ingresa_a_caja=True) | Q(es_efectivo=False),
                name="medio_pago_efectivo_ingresa_a_caja",
                violation_error_message="El efectivo ingresa a caja.",
            ),
        ]

    def __str__(self):
        return self.nombre


class Caja(ModeloBase):
    fecha = models.DateField()
    turno = models.CharField(max_length=6, choices=Turno.choices)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cajas_abiertas"
    )
    # Fondo de cambio, opcional; vacío se guarda 0 (DEC-38).
    monto_inicial = campo_monto(null=True, blank=True, validators=[NO_NEGATIVO])
    estado = models.CharField(max_length=7, choices=EstadoCaja.choices, default=EstadoCaja.ABIERTA)
    abierta_en = models.DateTimeField(default=timezone.now)
    cerrada_en = models.DateTimeField(null=True, blank=True)
    cerrada_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cajas_cerradas",
    )
    # Motivo de las diferencias del cierre (DEC-40).
    observacion_cierre = models.TextField(blank=True)

    class Meta:
        db_table = "caja"
        constraints = [
            models.CheckConstraint(condition=Q(turno__in=Turno.values), name="caja_turno_valido"),
            models.CheckConstraint(
                condition=Q(estado__in=EstadoCaja.values), name="caja_estado_valido"
            ),
            # RI-01 (DEC-83): una sola caja abierta a la vez, de cualquier fecha y turno. Puede
            # haber varias cajas por fecha y turno; las cerradas no se reabren.
            models.UniqueConstraint(
                fields=["estado"],
                condition=Q(estado=EstadoCaja.ABIERTA),
                name="caja_una_sola_abierta",
                violation_error_message="Ya hay una caja abierta.",
            ),
            models.CheckConstraint(
                condition=Q(cerrada_en__isnull=True) | Q(estado=EstadoCaja.CERRADA),
                name="caja_cerrada_en_solo_si_cerrada",
            ),
            models.CheckConstraint(
                condition=Q(monto_inicial__gte=0), name="caja_monto_inicial_no_negativo"
            ),
        ]

    def __str__(self):
        return f"{self.fecha} {self.get_turno_display()} ({self.get_estado_display()})"


class CierreCajaDetalle(ModeloBase):
    caja = models.ForeignKey(Caja, on_delete=models.PROTECT)
    medio_pago = models.ForeignKey(MedioPago, on_delete=models.PROTECT)
    monto_sistema = campo_monto()
    monto_contado = campo_monto(validators=[NO_NEGATIVO])

    class Meta:
        db_table = "cierre_caja_detalle"
        constraints = [
            models.UniqueConstraint(
                fields=["caja", "medio_pago"], name="cierre_caja_detalle_caja_medio_unico"
            ),
            models.CheckConstraint(
                condition=Q(monto_contado__gte=0), name="cierre_caja_detalle_contado_no_negativo"
            ),
        ]

    def __str__(self):
        return f"{self.caja} - {self.medio_pago}"


def _solo_referencia(venta=False, pago_cliente=False, pago_proveedor=False):
    return Q(
        venta__isnull=not venta,
        pago_cliente__isnull=not pago_cliente,
        pago_proveedor__isnull=not pago_proveedor,
    )


class MovimientoCaja(ModeloBase):
    """Implementa SC-02. El monto es siempre positivo; el signo lo da el tipo."""

    caja = models.ForeignKey(Caja, on_delete=models.PROTECT)
    fecha_hora = models.DateTimeField(default=timezone.now)
    tipo = models.CharField(max_length=7, choices=TipoMovimientoCaja.choices)
    monto = campo_monto(validators=[validar_positivo])
    medio_pago = models.ForeignKey(MedioPago, on_delete=models.PROTECT)
    concepto = models.CharField(max_length=15, choices=ConceptoMovimientoCaja.choices)
    venta = models.ForeignKey("ventas.Venta", on_delete=models.PROTECT, null=True, blank=True)
    pago_cliente = models.ForeignKey(
        "clientes.PagoCliente", on_delete=models.PROTECT, null=True, blank=True
    )
    pago_proveedor = models.ForeignKey(
        "proveedores.PagoProveedor", on_delete=models.PROTECT, null=True, blank=True
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "movimiento_caja"
        verbose_name = "movimiento de caja"
        verbose_name_plural = "movimientos de caja"
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name="movimiento_caja_monto_positivo"),
            models.CheckConstraint(
                condition=Q(tipo__in=TipoMovimientoCaja.values),
                name="movimiento_caja_tipo_valido",
            ),
            models.CheckConstraint(
                condition=Q(concepto__in=ConceptoMovimientoCaja.values),
                name="movimiento_caja_concepto_valido",
            ),
            # RI-13: exactamente la referencia que corresponde al concepto; OTRO no lleva ninguna.
            models.CheckConstraint(
                condition=(
                    Q(concepto__in=[ConceptoMovimientoCaja.VENTA, ConceptoMovimientoCaja.ANULACION])
                    & _solo_referencia(venta=True)
                    | Q(
                        concepto__in=[
                            ConceptoMovimientoCaja.PAGO_CLIENTE,
                            ConceptoMovimientoCaja.ANULACION_COBRO,
                        ]
                    )
                    & _solo_referencia(pago_cliente=True)
                    | Q(
                        concepto__in=[
                            ConceptoMovimientoCaja.PAGO_PROVEEDOR,
                            ConceptoMovimientoCaja.ANULACION_PAGO,
                        ]
                    )
                    & _solo_referencia(pago_proveedor=True)
                    | Q(concepto=ConceptoMovimientoCaja.OTRO) & _solo_referencia()
                ),
                name="movimiento_caja_referencia_segun_concepto",
            ),
            # DEC-68: la anulación es siempre un egreso, y una venta tiene a lo sumo una.
            models.CheckConstraint(
                condition=~Q(concepto=ConceptoMovimientoCaja.ANULACION)
                | Q(tipo=TipoMovimientoCaja.EGRESO),
                name="movimiento_caja_anulacion_es_egreso",
            ),
            models.UniqueConstraint(
                fields=["venta"],
                condition=Q(concepto=ConceptoMovimientoCaja.ANULACION),
                name="movimiento_caja_una_anulacion_por_venta",
                violation_error_message="La venta ya tiene su anulación.",
            ),
            # DEC-92: la reversa de un pago es un ingreso; un pago tiene un egreso y una reversa.
            models.CheckConstraint(
                condition=~Q(concepto=ConceptoMovimientoCaja.ANULACION_PAGO)
                | Q(tipo=TipoMovimientoCaja.INGRESO),
                name="movimiento_caja_anulacion_pago_es_ingreso",
            ),
            models.UniqueConstraint(
                fields=["pago_proveedor", "concepto"],
                condition=Q(pago_proveedor__isnull=False),
                name="movimiento_caja_un_movimiento_por_pago_y_concepto",
                violation_error_message="El pago ya tiene ese movimiento de caja.",
            ),
            # DEC-113: la reversa de un cobro es un egreso; un cobro tiene un ingreso y una reversa.
            models.CheckConstraint(
                condition=~Q(concepto=ConceptoMovimientoCaja.ANULACION_COBRO)
                | Q(tipo=TipoMovimientoCaja.EGRESO),
                name="movimiento_caja_anulacion_cobro_es_egreso",
            ),
            models.UniqueConstraint(
                fields=["pago_cliente", "concepto"],
                condition=Q(pago_cliente__isnull=False),
                name="movimiento_caja_un_movimiento_por_cobro_y_concepto",
                violation_error_message="El cobro ya tiene ese movimiento de caja.",
            ),
        ]
        indexes = [
            models.Index(fields=["caja", "medio_pago"], name="mov_caja_caja_medio_idx"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.monto} ({self.get_concepto_display()})"
