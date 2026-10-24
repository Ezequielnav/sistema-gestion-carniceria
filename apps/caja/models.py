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
    """Lista final a confirmar (PR-10)."""

    VENTA = "VENTA", "Venta"
    PAGO_CLIENTE = "PAGO_CLIENTE", "Pago de cliente"
    PAGO_PROVEEDOR = "PAGO_PROVEEDOR", "Pago a proveedor"
    OTRO = "OTRO", "Otro"


class MedioPago(ModeloBase):
    """Valores a confirmar (PR-08)."""

    nombre = models.CharField(max_length=50)
    ingresa_a_caja = models.BooleanField(default=True)
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
        ]

    def __str__(self):
        return self.nombre


class Caja(ModeloBase):
    fecha = models.DateField()
    turno = models.CharField(max_length=6, choices=Turno.choices)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cajas_abiertas"
    )
    # Fondo de cambio (a confirmar: PR-05).
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
    # Para diferencias (a confirmar: PR-07).
    observacion_cierre = models.TextField(blank=True)

    class Meta:
        db_table = "caja"
        constraints = [
            models.CheckConstraint(condition=Q(turno__in=Turno.values), name="caja_turno_valido"),
            models.CheckConstraint(
                condition=Q(estado__in=EstadoCaja.values), name="caja_estado_valido"
            ),
            # RI-01: una sola caja abierta por fecha y turno.
            models.UniqueConstraint(
                fields=["fecha", "turno"],
                condition=Q(estado=EstadoCaja.ABIERTA),
                name="caja_abierta_unica_por_fecha_turno",
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
    concepto = models.CharField(max_length=14, choices=ConceptoMovimientoCaja.choices)
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
                    Q(concepto=ConceptoMovimientoCaja.VENTA) & _solo_referencia(venta=True)
                    | Q(concepto=ConceptoMovimientoCaja.PAGO_CLIENTE)
                    & _solo_referencia(pago_cliente=True)
                    | Q(concepto=ConceptoMovimientoCaja.PAGO_PROVEEDOR)
                    & _solo_referencia(pago_proveedor=True)
                    | Q(concepto=ConceptoMovimientoCaja.OTRO) & _solo_referencia()
                ),
                name="movimiento_caja_referencia_segun_concepto",
            ),
        ]
        indexes = [
            models.Index(fields=["caja", "medio_pago"], name="mov_caja_caja_medio_idx"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.monto} ({self.get_concepto_display()})"
