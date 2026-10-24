from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.comun.models import NO_NEGATIVO, ModeloBase, campo_cantidad, campo_monto


class UnidadMedida(models.TextChoices):
    """A confirmar (PR-03)."""

    UNIDAD = "UNIDAD", "Unidad"
    KG = "KG", "Kilogramo"


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
    # Código interno de la carnicería, único si existe (a confirmar: PR-04). Nulo cuando no hay
    # código, para que el único parcial lo ignore.
    plus_interno = models.CharField(max_length=30, null=True, blank=True)  # noqa: DJ001
    precio_venta = campo_monto(validators=[NO_NEGATIVO])
    unidad_medida = models.CharField(max_length=6, choices=UnidadMedida.choices)
    # false para los productos cárnicos (a confirmar: PR-01).
    controla_stock = models.BooleanField()
    # Se actualiza solo con ventas e ingresos (RI-07).
    stock_actual = campo_cantidad(default=0)
    # Umbral de alerta (a confirmar: PR-20).
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
