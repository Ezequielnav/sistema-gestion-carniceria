from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo.forms import ProductoForm
from apps.catalogo.services import crear_producto, puede_crear
from apps.comun.permisos import requiere_funcion
from apps.ventas.forms import AnularVentaForm, ConfirmarVentaForm
from apps.ventas.models import Venta
from apps.ventas.services import (
    anular_venta,
    buscar_para_venta,
    problema_para_vender,
    puede_vender,
    registrar_venta,
    ventas_de_la_caja_abierta,
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
        {
            "problema": problema_para_vender(),
            "form": ConfirmarVentaForm(),
            # A1: solo la cajera con permiso de alta (RN-05, DEC-63).
            "form_producto": ProductoForm(prefix="producto") if puede_crear(request.user) else None,
        },
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
def producto_nuevo(request):
    """CU-01 A1: alta de producto desde la venta con el servicio de CU-11 (RF-17, DEC-62)."""
    _solo_cajera(request)
    if not puede_crear(request.user):
        raise PermissionDenied
    form = ProductoForm(request.POST, prefix="producto")
    if form.is_valid():
        try:
            producto = crear_producto(request.user, form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return JsonResponse({"producto": _producto(producto)})
    # Por campo, para mostrarlos junto a cada uno; "__all__" son los generales.
    errores = {campo: list(lista) for campo, lista in form.errors.items()}
    return JsonResponse({"errores": errores}, status=400)


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


# Anulación: pantallas del Administrador (DEC-45, DEC-71)


@requiere_funcion("Ventas del turno")
@require_GET
def lista(request):
    """Ventas de la caja abierta, con su estado (DEC-71)."""
    caja, ventas = ventas_de_la_caja_abierta()
    return render(request, "ventas/lista.html", {"caja": caja, "ventas": ventas})


def _detalle(request, venta, form, status=200):
    detalles = venta.detalleventa_set.select_related("producto").order_by("pk")
    return render(
        request,
        "ventas/detalle.html",
        {"venta": venta, "detalles": detalles, "form": form},
        status=status,
    )


def _venta(pk):
    return get_object_or_404(
        Venta.objects.select_related("caja", "usuario", "medio_pago", "anulada_por_usuario"),
        pk=pk,
    )


@requiere_funcion("Ventas del turno")
@require_GET
def detalle(request, pk):
    return _detalle(request, _venta(pk), AnularVentaForm())


@requiere_funcion("Ventas del turno")
@require_POST
def anular(request, pk):
    """Anula con motivo y revierte caja y stock en el servicio (DEC-45, DEC-66)."""
    venta = _venta(pk)
    form = AnularVentaForm(request.POST)
    if form.is_valid():
        try:
            anular_venta(request.user, venta, form.cleaned_data["motivo"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Se anuló la venta N.º {venta.pk}.")
            return redirect("ventas:detalle", pk=venta.pk)
    return _detalle(request, _venta(pk), form, status=400)
