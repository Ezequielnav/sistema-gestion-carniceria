from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.formats import number_format

from apps.comun.models import NO_NEGATIVO, ModeloBase, campo_cantidad, campo_monto


class UnidadMedida(models.TextChoices):
    """Unidad o kg, elegida por producto (DEC-79, supuesto del proyecto; ex PR-03)."""

    UNIDAD = "UNIDAD", "Unidad"
    KG = "KG", "Kilogramo"


def formatear_cantidad(cantidad, unidad):
    """Cantidad para mostrar: por unidad, entera ("2"); por kg, con 3 decimales y coma ("1,250 kg").

    Única forma de mostrar cantidades de venta e ingreso (panel, detalle y ticket).
    """
    if unidad == UnidadMedida.KG:
        return f"{number_format(cantidad, 3, use_l10n=True)} kg"
    return number_format(cantidad, 0, use_l10n=True)


def cantidad_para_editar(cantidad, unidad):
    """Valor inicial de un campo de cantidad: entero por unidad ("6", no "6,000"; DEC-48).

    Los campos editables no llevan "kg"; por kg quedan los 3 decimales.
    """
    if cantidad is None or unidad != UnidadMedida.UNIDAD:
        return cantidad
    return cantidad.quantize(Decimal(1))


class Categoria(ModeloBase):
    nombre = models.CharField(max_length=80)

    class Meta:
        db_table = "categoria"
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        constraints = [
            # Sin distinguir mayúsculas, como medio_pago.
            models.UniqueConstraint(
                Lower("nombre"),
                name="categoria_nombre_unico",
                violation_error_message="Ya existe una categoría con ese nombre.",
            ),
        ]

    def __str__(self):
        return self.nombre


class Producto(ModeloBase):
    nombre = models.CharField(max_length=120)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, null=True, blank=True)
    # Código interno de la carnicería, único si existe (DEC-37). Nulo cuando no hay
    # código, para que el único parcial lo ignore.
    plus_interno = models.CharField(max_length=30, null=True, blank=True)  # noqa: DJ001
    precio_venta = campo_monto(validators=[NO_NEGATIVO])
    unidad_medida = models.CharField(max_length=6, choices=UnidadMedida.choices)
    # false para los productos cárnicos (DEC-36).
    controla_stock = models.BooleanField()
    # Lo cambian solo ventas, ingresos y ajustes, con mover_stock (RI-07, DEC-96).
    stock_actual = campo_cantidad(default=0)
    # Umbral de alerta (DEC-82, DEC-101; supuestos, ex PR-20).
    stock_minimo = campo_cantidad(null=True, blank=True, validators=[NO_NEGATIVO])
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "producto"
        constraints = [
            models.UniqueConstraint(
                fields=["plus_interno"],
                condition=Q(plus_interno__isnull=False),
                name="producto_plus_interno_unico",
                violation_error_message="Ya existe un producto con ese plus interno.",
            ),
            models.CheckConstraint(
                condition=Q(plus_interno__isnull=True) | ~Q(plus_interno=""),
                name="producto_plus_interno_no_vacio",
                violation_error_message="El plus interno no puede quedar vacío.",
            ),
            models.CheckConstraint(
                condition=Q(precio_venta__gte=0), name="producto_precio_venta_no_negativo"
            ),
            models.CheckConstraint(
                condition=Q(stock_minimo__gte=0), name="producto_stock_minimo_no_negativo"
            ),
            models.CheckConstraint(
                condition=Q(unidad_medida__in=UnidadMedida.values),
                name="producto_unidad_medida_valida",
            ),
        ]
        indexes = [
            models.Index(fields=["nombre"], name="producto_nombre_idx"),
        ]

    def __str__(self):
        return self.nombre


class MotivoAjuste(models.TextChoices):
    """Motivo de un cambio de stock hecho a mano (DEC-98, supuesto del proyecto; ex PR-32)."""

    MODIFICACION_MANUAL = "MODIFICACION_MANUAL", "Modificación manual"
    CONTEO = "CONTEO", "Conteo"
    VENCIMIENTO = "VENCIMIENTO", "Vencimiento"
    ROTURA = "ROTURA", "Rotura"
    OTRO = "OTRO", "Otro"
    # Solo en el alta del producto (DEC-99); no se elige al modificar.
    STOCK_INICIAL = "STOCK_INICIAL", "Stock inicial"


class AjusteStock(ModeloBase):
    """Cambio de stock hecho a mano al crear o modificar un producto (CU-11, DEC-98).

    Lo registra el servicio de catálogo; no se edita ni se borra (RI-17).
    """

    fecha_hora = models.DateTimeField(default=timezone.now)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    # Stock al guardar el ajuste: copia histórica, puede ser negativo (DEC-46).
    stock_anterior = campo_cantidad()
    stock_nuevo = campo_cantidad(validators=[NO_NEGATIVO])
    motivo = models.CharField(max_length=19, choices=MotivoAjuste.choices)

    class Meta:
        db_table = "ajuste_stock"
        verbose_name = "ajuste de stock"
        verbose_name_plural = "ajustes de stock"
        constraints = [
            models.CheckConstraint(
                condition=Q(stock_nuevo__gte=0), name="ajuste_stock_nuevo_no_negativo"
            ),
            models.CheckConstraint(
                condition=Q(motivo__in=MotivoAjuste.values), name="ajuste_stock_motivo_valido"
            ),
        ]
        indexes = [
            models.Index(fields=["producto", "fecha_hora"], name="ajuste_stock_producto_idx"),
        ]

    def __str__(self):
        return f"Ajuste {self.pk} - {self.producto}"
