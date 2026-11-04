"""Pestaña "Resumen" de Reportes (RF-55, DEC-158): un tablero de solo lectura para un rango.

Cada número sale de un servicio que ya existe (reportes de CU-09, clientes, proveedores y
catálogo), así el Resumen muestra lo mismo que cada pestaña; acá solo se suma y se divide.
Ventas, ingresos y gráficos son del rango; saldos de clientes y proveedores y stock bajo,
de hoy, porque no dependen de un período.
"""

import datetime
from decimal import Decimal

from apps.catalogo.services import cantidad_con_stock_bajo
from apps.clientes.models import Cliente
from apps.clientes.services import deudas_vencidas_de_clientes, saldos_de_clientes
from apps.proveedores.models import Proveedor
from apps.proveedores.services import saldos_de_proveedores
from apps.reportes import services

TOP = 5
CERO = Decimal("0.00")
CENTAVO = Decimal("0.01")


def tablero(usuario, desde, hasta):
    """Datos del Resumen; los permisos son los de los reportes (DEC-134)."""
    ventas = services.ventas_diarias(usuario, desde, hasta)
    ingresos = services.ingresos_por_dia(usuario, desde, hasta)
    medios = services.totales_por_medio(usuario, desde, hasta)
    productos = services.productos_mas_vendidos(usuario, desde, hasta)

    # Totales de los mismos cálculos que el listado de clientes y el de proveedores (DEC-21).
    clientes = list(Cliente.objects.only("pk"))
    proveedores = list(Proveedor.objects.only("pk"))
    saldo_clientes = sum(saldos_de_clientes(clientes).values(), CERO)
    vencida = sum(deudas_vencidas_de_clientes(clientes).values(), CERO)
    deuda_proveedores = sum(saldos_de_proveedores(proveedores).values(), CERO)

    por_dia = {dia["fecha"]: dia["total"] for dia in ventas["dias"]}
    dias = (hasta - desde).days + 1
    serie = [
        (fecha, por_dia.get(fecha, CERO))
        for fecha in (desde + datetime.timedelta(days=n) for n in range(dias))
    ]
    cantidad = ventas["cantidad"]
    return {
        "ventas": {"cantidad": cantidad, "total": ventas["total"]},
        "ticket_promedio": (ventas["total"] / cantidad).quantize(CENTAVO) if cantidad else None,
        "ingresos": ingresos["totales"] if ingresos["dias"] else None,
        "cuentas_corrientes": (
            {"saldo": saldo_clientes, "vencida": vencida} if saldo_clientes or vencida else None
        ),
        "stock_bajo": cantidad_con_stock_bajo(),
        "deuda_proveedores": deuda_proveedores,
        "serie": serie if cantidad else [],
        "medios": [m for m in medios["medios"] if m["cantidad"]],
        "top": list(productos["productos"][:TOP]),
    }
