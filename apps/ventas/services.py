"""Reglas de CU-01 Registrar venta, y el resumen del inicio."""

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.caja.models import Caja, EstadoCaja, MedioPago
from apps.caja.services import caja_abierta, registrar_ingreso_venta
from apps.catalogo.models import Producto, UnidadMedida
from apps.catalogo.services import buscar_productos
from apps.usuarios.models import Rol
from apps.ventas.models import DetalleVenta, Venta

CENTAVO = Decimal("0.01")
MILESIMA = Decimal("0.001")


def resumen_del_dia(fecha):
    """Cantidad y monto total de las ventas de una fecha (hora local)."""
    datos = Venta.objects.filter(fecha_hora__date=fecha).aggregate(
        cantidad=Count("id"), total=Sum("monto_total")
    )
    return datos["cantidad"], datos["total"] or Decimal("0.00")


def ultimas_ventas(limite=5):
    return list(
        Venta.objects.select_related("medio_pago", "cliente").order_by("-fecha_hora")[:limite]
    )


def puede_vender(usuario):
    """CU-01: solo la cajera (matriz de actores de 04)."""
    return usuario.rol == Rol.CAJERA


def medios_de_pago_para_venta():
    """Medios activos que ingresan a caja: cuenta corriente no se ofrece hasta H4 (DEC-41)."""
    return MedioPago.objects.filter(activo=True, ingresa_a_caja=True).order_by("pk")


def buscar_para_venta(texto, limite=20):
    """Activos por nombre o plus, y el que coincide exacto con el plus (DEC-37, DEC-52)."""
    texto = texto.strip()
    if not texto:
        return None, []
    exacto = Producto.objects.filter(activo=True, plus_interno=texto).first()
    return exacto, list(buscar_productos(texto)[:limite])


def subtotal(cantidad, precio):
    """Cantidad × precio, redondeado a centavos con la mitad hacia arriba (DEC-49)."""
    return (cantidad * precio).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _validar_cantidad(producto, cantidad):
    """Mayor a 0 (RI-16); entera por unidad y hasta 3 decimales por kg (DEC-48)."""
    if cantidad <= 0:
        raise ValidationError(f"La cantidad de {producto} tiene que ser mayor a 0.")
    if producto.unidad_medida == UnidadMedida.UNIDAD and cantidad != cantidad.to_integral_value():
        raise ValidationError(f"{producto} se vende por unidad: la cantidad tiene que ser entera.")
    if cantidad != cantidad.quantize(MILESIMA):
        raise ValidationError(f"La cantidad de {producto} admite hasta 3 decimales.")


def _verificar_caja(caja):
    """Se vende en la única caja abierta (DEC-39), que tiene que ser de hoy (DEC-50)."""
    if caja is None:
        raise ValidationError("No hay una caja abierta. Abrí la caja para vender.", code="sin_caja")
    if caja.fecha != timezone.localdate():
        raise ValidationError(
            "La caja abierta es de otro día. Hay que cerrarla y abrir la de hoy para vender.",
            code="caja_de_otro_dia",
        )


def problema_para_vender():
    """Por qué no se puede vender ahora (sin caja o caja de otro día), o None (CU-01 A4)."""
    try:
        _verificar_caja(caja_abierta())
    except ValidationError as error:
        return error.messages[0]
    return None


def _caja_para_vender():
    """La caja de la venta, con su fila bloqueada hasta terminar la operación."""
    caja = Caja.objects.select_for_update().filter(estado=EstadoCaja.ABIERTA).first()
    _verificar_caja(caja)
    return caja


def _agrupar(lineas):
    """Un producto repetido suma su cantidad a la misma línea (DEC-53)."""
    agrupadas = {}
    for producto_id, cantidad in lineas:
        agrupadas[producto_id] = agrupadas.get(producto_id, Decimal("0")) + cantidad
    return agrupadas


def registrar_venta(usuario, lineas, medio_pago):
    """Registra la venta completa o nada (RNF-10).

    `lineas` es una lista de (id de producto, cantidad). Precios, subtotales y total se
    calculan acá, nunca se toman del navegador (RI-12, RI-03, DEC-47). Devuelve la venta y
    los avisos de stock insuficiente (DEC-46).
    """
    if not puede_vender(usuario):
        raise PermissionDenied("Solo la cajera puede registrar ventas.")
    if not lineas:
        raise ValidationError("La venta no tiene productos.", code="sin_productos")
    if not medios_de_pago_para_venta().filter(pk=medio_pago.pk).exists():
        raise ValidationError(
            {"medio_pago": "Ese medio de pago no se puede usar en la venta."}, code="medio_pago"
        )
    cantidades = _agrupar(lineas)
    with transaction.atomic():
        caja = _caja_para_vender()
        productos = Producto.objects.select_for_update().in_bulk(list(cantidades))
        detalles = []
        for producto_id, cantidad in cantidades.items():
            producto = productos.get(producto_id)
            if producto is None or not producto.activo:
                raise ValidationError("Uno de los productos ya no está disponible.")
            _validar_cantidad(producto, cantidad)
            precio = producto.precio_venta
            detalles.append(
                DetalleVenta(
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal(cantidad, precio),
                )
            )
        total = sum((d.subtotal for d in detalles), Decimal("0"))
        if total <= 0:
            # El ingreso de caja tiene que ser mayor a 0 (RI-04, movimiento_caja_monto_positivo).
            raise ValidationError("El total de la venta tiene que ser mayor a 0.")
        venta = Venta.objects.create(
            caja=caja, usuario=usuario, medio_pago=medio_pago, monto_total=total
        )
        for detalle in detalles:
            detalle.venta = venta
        DetalleVenta.objects.bulk_create(detalles)
        registrar_ingreso_venta(venta)
        avisos = []
        for detalle in detalles:
            producto = detalle.producto
            if not producto.controla_stock:
                continue  # La carne no lleva stock (RI-07, DEC-36).
            if producto.stock_actual < detalle.cantidad:
                # Sin cantidades: la cajera no consulta stock (DEC-33).
                avisos.append(
                    f"Stock insuficiente de {producto}: la venta se registró y el stock quedó "
                    "negativo. Avisale al administrador."
                )
            Producto.objects.filter(pk=producto.pk).update(
                stock_actual=F("stock_actual") - detalle.cantidad
            )
    return venta, avisos
