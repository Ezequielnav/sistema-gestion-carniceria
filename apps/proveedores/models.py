from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalogo.models import formatear_cantidad
from apps.comun.models import NO_NEGATIVO, ModeloBase, campo_cantidad, campo_monto, validar_positivo


class EstadoIngreso(models.TextChoices):
    """Un ingreso no se edita: el Administrador lo anula con motivo (DEC-92)."""

    VIGENTE = "VIGENTE", "Vigente"
    ANULADO = "ANULADO", "Anulado"


class CondicionPago(models.TextChoices):
    """A crédito deja la deuda; contado registra el pago (DEC-81, supuesto; ex PR-18)."""

    CONTADO = "CONTADO", "Contado"
    A_CREDITO = "A_CREDITO", "A crédito"


class Proveedor(ModeloBase):
    nombre = models.CharField(max_length=120)
    # Datos de contacto a confirmar (PR-31).
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "proveedor"
        verbose_name_plural = "proveedores"

    def __str__(self):
        return self.nombre


class ProductoProveedor(ModeloBase):
    producto = models.ForeignKey("catalogo.Producto", on_delete=models.PROTECT)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    # Último precio conocido; sugiere el precio en CU-05.
    precio_compra = campo_monto(validators=[NO_NEGATIVO])

    class Meta:
        db_table = "producto_proveedor"
        verbose_name = "producto de proveedor"
        verbose_name_plural = "productos de proveedor"
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "proveedor"],
                name="producto_proveedor_unico",
                violation_error_message="Ese proveedor ya tiene un precio para este producto.",
            ),
            models.CheckConstraint(
                condition=Q(precio_compra__gte=0),
                name="producto_proveedor_precio_no_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.producto} - {self.proveedor}"


class IngresoMercaderia(ModeloBase):
    fecha = models.DateField()
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    total = campo_monto(validators=[NO_NEGATIVO])
    condicion_pago = models.CharField(max_length=9, choices=CondicionPago.choices)
    # Número de remito o de factura, y su fecha si hace falta (DEC-81, DEC-93).
    observacion = models.CharField(max_length=255, blank=True)
    estado = models.CharField(
        max_length=7, choices=EstadoIngreso.choices, default=EstadoIngreso.VIGENTE
    )
    anulado_en = models.DateTimeField(null=True, blank=True)
    anulado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ingresos_anulados",
    )
    motivo_anulacion = models.TextField(blank=True)

    class Meta:
        db_table = "ingreso_mercaderia"
        verbose_name = "ingreso de mercadería"
        verbose_name_plural = "ingresos de mercadería"
        constraints = [
            models.CheckConstraint(
                condition=Q(total__gte=0), name="ingreso_mercaderia_total_no_negativo"
            ),
            models.CheckConstraint(
                condition=Q(condicion_pago__in=CondicionPago.values),
                name="ingreso_mercaderia_condicion_pago_valida",
            ),
            models.CheckConstraint(
                condition=Q(estado__in=EstadoIngreso.values),
                name="ingreso_mercaderia_estado_valido",
            ),
            # Los datos de la anulación están si y solo si el ingreso está anulado (DEC-92).
            models.CheckConstraint(
                condition=(
                    Q(
                        estado=EstadoIngreso.ANULADO,
                        anulado_en__isnull=False,
                        anulado_por_usuario__isnull=False,
                    )
                    & ~Q(motivo_anulacion="")
                )
                | Q(
                    estado=EstadoIngreso.VIGENTE,
                    anulado_en__isnull=True,
                    anulado_por_usuario__isnull=True,
                    motivo_anulacion="",
                ),
                name="ingreso_mercaderia_datos_de_anulacion_segun_estado",
            ),
        ]

    def __str__(self):
        return f"Ingreso {self.pk} - {self.proveedor}"


class DetalleIngreso(ModeloBase):
    ingreso = models.ForeignKey(IngresoMercaderia, on_delete=models.PROTECT)
    producto = models.ForeignKey("catalogo.Producto", on_delete=models.PROTECT)
    cantidad = campo_cantidad(validators=[validar_positivo])
    precio_unitario = campo_monto(validators=[NO_NEGATIVO])
    # Solo para productos con vencimiento (a confirmar: PR-21).
    fecha_vencimiento = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "detalle_ingreso"
        verbose_name = "detalle de ingreso"
        verbose_name_plural = "detalles de ingreso"
        constraints = [
            models.CheckConstraint(
                condition=Q(cantidad__gt=0), name="detalle_ingreso_cantidad_positiva"
            ),
            models.CheckConstraint(
                condition=Q(precio_unitario__gte=0), name="detalle_ingreso_precio_no_negativo"
            ),
        ]
        indexes = [
            models.Index(
                fields=["fecha_vencimiento"],
                condition=Q(fecha_vencimiento__isnull=False),
                name="det_ingreso_vencimiento_idx",
            ),
        ]

    def __str__(self):
        return f"{self.producto} x {formatear_cantidad(self.cantidad, self.producto.unidad_medida)}"


class EstadoPago(models.TextChoices):
    """Un pago no se edita: el Administrador lo anula con motivo (DEC-92)."""

    VIGENTE = "VIGENTE", "Vigente"
    ANULADO = "ANULADO", "Anulado"


class PagoProveedor(ModeloBase):
    fecha_hora = models.DateTimeField(default=timezone.now)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    # Deuda que se paga; RI-14 (mismo proveedor que el ingreso) se valida en el servicio.
    ingreso = models.ForeignKey(IngresoMercaderia, on_delete=models.PROTECT, null=True, blank=True)
    monto = campo_monto(validators=[validar_positivo])
    medio_pago = models.ForeignKey("caja.MedioPago", on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    # Solo un pago en efectivo puede salir de la caja abierta; así tiene egreso (DEC-106).
    sale_de_caja = models.BooleanField(default=False)
    estado = models.CharField(max_length=7, choices=EstadoPago.choices, default=EstadoPago.VIGENTE)
    anulado_en = models.DateTimeField(null=True, blank=True)
    anulado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagos_proveedor_anulados",
    )
    motivo_anulacion = models.TextField(blank=True)

    class Meta:
        db_table = "pago_proveedor"
        verbose_name = "pago a proveedor"
        verbose_name_plural = "pagos a proveedores"
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name="pago_proveedor_monto_positivo"),
            models.CheckConstraint(
                condition=Q(estado__in=EstadoPago.values), name="pago_proveedor_estado_valido"
            ),
            # Los datos de la anulación están si y solo si el pago está anulado (DEC-92).
            models.CheckConstraint(
                condition=(
                    Q(
                        estado=EstadoPago.ANULADO,
                        anulado_en__isnull=False,
                        anulado_por_usuario__isnull=False,
                    )
                    & ~Q(motivo_anulacion="")
                )
                | Q(
                    estado=EstadoPago.VIGENTE,
                    anulado_en__isnull=True,
                    anulado_por_usuario__isnull=True,
                    motivo_anulacion="",
                ),
                name="pago_proveedor_datos_de_anulacion_segun_estado",
            ),
        ]

    def __str__(self):
        return f"Pago {self.pk} - {self.proveedor}"
