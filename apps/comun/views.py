from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.caja.services import cajas_abiertas
from apps.catalogo.services import (
    cantidad_con_stock_bajo,
    cantidad_de_productos_activos,
    puede_modificar,
)
from apps.ventas.services import resumen_del_dia, ultimas_ventas


@login_required
def inicio(request):
    cantidad_ventas, total_ventas = resumen_del_dia(timezone.localdate())
    return render(
        request,
        "comun/inicio.html",
        {
            "cantidad_ventas": cantidad_ventas,
            "total_ventas": total_ventas,
            "cajas_abiertas": cajas_abiertas(),
            "productos_activos": cantidad_de_productos_activos(),
            "ultimas_ventas": ultimas_ventas(),
            # Solo el Administrador; qué ve la cajera sigue pendiente (DEC-82, L9, PR-35).
            "stock_bajo": cantidad_con_stock_bajo() if puede_modificar(request.user) else None,
        },
    )
