from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.caja.services import caja_abierta, cajas_abiertas
from apps.catalogo.services import (
    cantidad_con_stock_bajo,
    cantidad_de_productos_activos,
)
from apps.usuarios.models import Rol
from apps.ventas.services import resumen_del_dia, ultimas_ventas


@login_required
def inicio(request):
    """Inicio por rol (R-4, DEC-154): solo el Administrador ve los totales del negocio.

    La cajera ve el estado de la caja y sus tres operaciones (DEC-137, DEC-148) y el dueño,
    solo el acceso a Reportes (DEC-134, DEC-147); para ellos no se calcula ningún total.
    """
    if request.user.rol == Rol.CAJERA:
        return render(request, "comun/inicio_cajera.html", {"caja": caja_abierta()})
    if request.user.rol != Rol.ADMINISTRADOR:
        return render(request, "comun/inicio_duenio.html")
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
            "stock_bajo": cantidad_con_stock_bajo(),
        },
    )
