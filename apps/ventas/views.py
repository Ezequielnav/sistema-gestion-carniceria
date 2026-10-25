from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.comun.permisos import requiere_funcion
from apps.ventas.forms import ConfirmarVentaForm
from apps.ventas.models import Venta
from apps.ventas.services import (
    buscar_para_venta,
    problema_para_vender,
    puede_vender,
    registrar_venta,
)


def _solo_cajera(request):
    if not puede_vender(request.user):
        raise PermissionDenied


def _producto(producto):
    return {
        "id": producto.pk,
        "nombre": producto.nombre,
        "plus": producto.plus_interno or "",
        "precio": str(producto.precio_venta),
        "unidad": producto.unidad_medida,
    }


@requiere_funcion("Ventas")
@require_GET
def nueva(request):
    """CU-01: pantalla de venta. Sin caja abierta de hoy, avisa y enlaza a Caja (A4, DEC-50)."""
    _solo_cajera(request)
    return render(
        request,
        "ventas/nueva.html",
        {"problema": problema_para_vender(), "form": ConfirmarVentaForm()},
    )


@requiere_funcion("Ventas")
@require_GET
def buscar(request):
    """Búsqueda por nombre o plus y coincidencia exacta del lector (DEC-37, DEC-52)."""
    _solo_cajera(request)
    exacto, resultados = buscar_para_venta(request.GET.get("q", ""))
    return JsonResponse(
        {
            "exacto": _producto(exacto) if exacto else None,
            "resultados": [_producto(p) for p in resultados],
        }
    )


@requiere_funcion("Ventas")
@require_POST
def confirmar(request):
    """Registra la venta con lo que calcula el servidor (DEC-47) y devuelve la URL del ticket."""
    _solo_cajera(request)
    form = ConfirmarVentaForm(request.POST)
    if not form.is_valid():
        errores = [e for lista in form.errors.values() for e in lista]
        return JsonResponse({"errores": errores}, status=400)
    try:
        venta, avisos = registrar_venta(
            request.user, form.cleaned_data["lineas"], form.cleaned_data["medio_pago"]
        )
    except ValidationError as error:
        return JsonResponse({"errores": error.messages}, status=400)
    for aviso in avisos:
        messages.warning(request, aviso)
    return JsonResponse({"ticket": reverse("ventas:ticket", args=[venta.pk])})


@requiere_funcion("Ventas")
@require_GET
def ticket(request, pk):
    """Comprobante no fiscal para imprimir desde el navegador (DEC-44, DEC-54)."""
    _solo_cajera(request)
    venta = get_object_or_404(Venta.objects.select_related("usuario", "medio_pago"), pk=pk)
    detalles = venta.detalleventa_set.select_related("producto").order_by("pk")
    return render(request, "ventas/ticket.html", {"venta": venta, "detalles": detalles})
