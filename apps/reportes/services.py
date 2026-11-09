"""CU-09 Generar reportes (RF-42 a RF-45; DEC-136, DEC-140 a DEC-145).

Reportes a pedido, de solo lectura, calculados al consultar (DEC-21) con consultas agrupadas
(R-2). Las ventas se cuentan por la fecha y el turno de su caja (DEC-83, DEC-140): una caja
de otro día no recibe ventas (DEC-50). Los cobros, que pueden no tener caja (DEC-110), por la
fecha del cobro (DEC-157). Anuladas no cuentan.
"""

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Count, DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDate

from apps.caja.models import Caja, EstadoCaja, Turno
from apps.clientes.models import EstadoPagoCliente, PagoCliente
from apps.usuarios.models import Rol
from apps.ventas.models import DetalleVenta, EstadoVenta, Venta

CERO = Decimal("0.00")


def puede_ver(usuario):
    """El Administrador y los Dueños, en solo lectura (DEC-134, RF-45)."""
    return usuario.is_authenticated and usuario.rol in (Rol.ADMINISTRADOR, Rol.DUENIO)


def _exigir_permiso(usuario):
    if not puede_ver(usuario):
        raise PermissionDenied("Solo el administrador y los dueños ven los reportes.")


def _ventas(desde, hasta):
    return Venta.objects.filter(estado=EstadoVenta.CONFIRMADA, caja__fecha__range=(desde, hasta))


def _cobros(desde, hasta):
    # DEC-186: solo los vigentes, por la fecha del cobro; un cobro anulado con su caja ya
    # cerrada deja de contar acá, aunque el cierre de esa caja conserve el ingreso.
    return PagoCliente.objects.filter(
        estado=EstadoPagoCliente.VIGENTE, fecha_hora__date__range=(desde, hasta)
    )


def ventas_diarias(usuario, desde, hasta):
    """DEC-140: por fecha y turno de la caja, sumando las cajas de la misma fecha y turno
    (DEC-83); incluye las ventas a cuenta corriente."""
    _exigir_permiso(usuario)
    filas = (
        _ventas(desde, hasta)
        .values("caja__fecha", "caja__turno")
        .annotate(cantidad=Count("pk"), total=Sum("monto_total"))
        .order_by("caja__fecha", "caja__turno")
    )
    dias = {}
    for fila in filas:
        dia = dias.setdefault(
            fila["caja__fecha"],
            {"fecha": fila["caja__fecha"], "turnos": [], "cantidad": 0, "total": CERO},
        )
        dia["turnos"].append(
            {
                "turno": Turno(fila["caja__turno"]).label,
                "cantidad": fila["cantidad"],
                "total": fila["total"],
            }
        )
        dia["cantidad"] += fila["cantidad"]
        dia["total"] += fila["total"]
    dias = list(dias.values())
    return {
        "dias": dias,
        "cantidad": sum(d["cantidad"] for d in dias),
        "total": sum((d["total"] for d in dias), CERO),
    }


def productos_mas_vendidos(usuario, desde, hasta):
    """DEC-141: ranking por importe, con la cantidad en su unidad; incluye la carne."""
    _exigir_permiso(usuario)
    detalles = DetalleVenta.objects.filter(
        venta__estado=EstadoVenta.CONFIRMADA, venta__caja__fecha__range=(desde, hasta)
    )
    filas = (
        detalles.values("producto_id", "producto__nombre", "producto__unidad_medida")
        .annotate(cantidad=Sum("cantidad"), importe=Sum("subtotal"))
        .order_by("-importe", "producto__nombre", "producto_id")
    )
    total = detalles.aggregate(total=Coalesce(Sum("subtotal"), Value(CERO)))["total"]
    return {"productos": filas, "total": total}


def ingresos_por_dia(usuario, desde, hasta):
    """DEC-142: ventas que no son a cuenta corriente más cobros, sin anuladas, separando lo
    que entró a caja de lo que quedó fuera (cobros sin caja). No resta egresos."""
    _exigir_permiso(usuario)
    dias = {}

    def _dia(fecha):
        return dias.setdefault(
            fecha,
            {"fecha": fecha, "ventas": CERO, "cobros": CERO, "en_caja": CERO, "fuera": CERO},
        )

    ventas = (
        _ventas(desde, hasta)
        .filter(medio_pago__ingresa_a_caja=True)
        .values("caja__fecha")
        .annotate(total=Sum("monto_total"))
    )
    for fila in ventas:
        dia = _dia(fila["caja__fecha"])
        dia["ventas"] += fila["total"]
        # Toda venta que no es a cuenta corriente entra a la caja abierta (DEC-41).
        dia["en_caja"] += fila["total"]
    cobros = (
        _cobros(desde, hasta)
        .annotate(dia=TruncDate("fecha_hora"))
        .values("dia", "entra_a_caja")
        .annotate(total=Sum("monto"))
    )
    for fila in cobros:
        dia = _dia(fila["dia"])
        dia["cobros"] += fila["total"]
        dia["en_caja" if fila["entra_a_caja"] else "fuera"] += fila["total"]
    filas = sorted(dias.values(), key=lambda d: d["fecha"])
    for dia in filas:
        dia["total"] = dia["en_caja"] + dia["fuera"]
    totales = {
        clave: sum((d[clave] for d in filas), CERO)
        for clave in ("ventas", "cobros", "en_caja", "fuera", "total")
    }
    return {"dias": filas, "totales": totales}


def totales_por_medio(usuario, desde, hasta):
    """DEC-143: por medio, ventas no anuladas (con la cuenta corriente) y cobros vigentes.
    El total de ventas coincide con el de ventas diarias."""
    _exigir_permiso(usuario)
    medios = {}

    def _medio(pk, nombre):
        return medios.setdefault(
            pk, {"medio": nombre, "cantidad": 0, "ventas": CERO, "cobros": CERO}
        )

    for fila in (
        _ventas(desde, hasta)
        .values("medio_pago_id", "medio_pago__nombre")
        .annotate(cantidad=Count("pk"), total=Sum("monto_total"))
    ):
        medio = _medio(fila["medio_pago_id"], fila["medio_pago__nombre"])
        medio["cantidad"] = fila["cantidad"]
        medio["ventas"] = fila["total"]
    for fila in (
        _cobros(desde, hasta)
        .values("medio_pago_id", "medio_pago__nombre")
        .annotate(total=Sum("monto"))
    ):
        _medio(fila["medio_pago_id"], fila["medio_pago__nombre"])["cobros"] = fila["total"]
    filas = [medios[pk] for pk in sorted(medios)]
    for medio in filas:
        medio["total"] = medio["ventas"] + medio["cobros"]
    totales = {
        "cantidad": sum(m["cantidad"] for m in filas),
        **{clave: sum((m[clave] for m in filas), CERO) for clave in ("ventas", "cobros", "total")},
    }
    return {"medios": filas, "totales": totales}


def cierres(usuario, desde, hasta):
    """DEC-144 (DEC-59): cajas cerradas del rango con la diferencia total del cierre, que se
    calcula y no se guarda (RI-10)."""
    _exigir_permiso(usuario)
    return (
        Caja.objects.filter(estado=EstadoCaja.CERRADA, fecha__range=(desde, hasta))
        .select_related("cerrada_por_usuario")
        .annotate(
            diferencia=Coalesce(
                Sum(F("cierrecajadetalle__monto_contado") - F("cierrecajadetalle__monto_sistema")),
                Value(CERO),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .order_by("fecha", "turno", "cerrada_en", "pk")
    )
