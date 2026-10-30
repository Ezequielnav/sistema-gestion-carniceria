from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo.forms import ProductoForm
from apps.catalogo.services import crear_producto, puede_crear
from apps.comun.permisos import requiere_funcion
from apps.ventas.forms import AnularVentaForm, ConfirmarVentaForm, HistorialVentasForm
from apps.ventas.services import (
    anular_venta,
    buscar_para_venta,
    detalles_de_venta,
    historial_de_ventas,
    obtener_venta,
    problema_para_vender,
    puede_anular,
    puede_vender,
    puede_ver_venta,
    registrar_venta,
    se_puede_anular,
    ventas_de_la_caja_abierta,
)

POR_PAGINA = 25
# Detalle y ticket: la cajera desde su caja y el Administrador desde el historial (DEC-84, DEC-86).
VER_VENTAS = ("Ventas de la caja", "Historial de ventas")


def _solo_cajera(request):
    if not puede_vender(request.user):
        raise PermissionDenied


def _venta(pk):
    try:
        return obtener_venta(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error


def _venta_visible(request, pk):
    """La venta, si el usuario puede ver su detalle y su ticket (DEC-84, L4)."""
    venta = _venta(pk)
    if not puede_ver_venta(request.user, venta):
        raise PermissionDenied
    return venta


def _producto(producto):
    return {
        "id": producto.pk,
        "nombre": producto.nombre,
        "plus": producto.plus_interno or "",
        "precio": str(producto.precio_venta),
        "unidad": producto.unidad_medida,
        # Para avisar al agregar, con la cantidad disponible; sin control, no avisa (DEC-102).
        "stock": str(producto.stock_actual) if producto.controla_stock else None,
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
    """Búsqueda por nombre o plus y coincidencia exacta del lector (DEC-37, DEC-52).

    Sin texto, trae los activos para elegir (DEC-97).
    """
    _solo_cajera(request)
    exacto, resultados, hay_mas = buscar_para_venta(request.GET.get("q", ""))
    return JsonResponse(
        {
            "exacto": _producto(exacto) if exacto else None,
            "resultados": [_producto(p) for p in resultados],
            "hay_mas": hay_mas,
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


@requiere_funcion(*VER_VENTAS)
@require_GET
def ticket(request, pk):
    """Comprobante no fiscal para imprimir desde el navegador (DEC-44, DEC-54, DEC-84)."""
    venta = _venta_visible(request, pk)
    return render(
        request,
        "ventas/ticket.html",
        {
            "venta": venta,
            "detalles": detalles_de_venta(venta),
            "puede_vender": puede_vender(request.user),
        },
    )


# Ventas de la caja (cajera, DEC-84) e historial de ventas (Administrador, DEC-86).
# Anular, solo el Administrador (DEC-45).


@requiere_funcion("Ventas de la caja")
@require_GET
def lista(request):
    """Ventas de la caja abierta, con su estado, sin anular (DEC-84)."""
    caja, ventas = ventas_de_la_caja_abierta()
    return render(request, "ventas/lista.html", {"caja": caja, "ventas": ventas})


@requiere_funcion("Historial de ventas")
@require_GET
def historial(request):
    """Ventas con filtros, paginadas; por defecto, las de la caja abierta (DEC-86)."""
    if not puede_anular(request.user):
        raise PermissionDenied
    form = HistorialVentasForm(request.GET or None)
    filtros = form.cleaned_data if form.is_bound and form.is_valid() else {}
    ventas, caja_por_defecto = historial_de_ventas(**filtros)
    pagina = Paginator(ventas, POR_PAGINA).get_page(request.GET.get("pagina"))
    consulta = request.GET.copy()
    consulta.pop("pagina", None)
    return render(
        request,
        "ventas/historial.html",
        {
            "form": form,
            "pagina": pagina,
            "caja_por_defecto": caja_por_defecto,
            "filtrado": any(filtros.values()),
            "consulta": consulta.urlencode(),
        },
    )


def _detalle(request, venta, form, status=200):
    return render(
        request,
        "ventas/detalle.html",
        {
            "venta": venta,
            "detalles": detalles_de_venta(venta),
            "form": form,
            "puede_anular": puede_anular(request.user),
            "volver": "ventas:historial" if puede_anular(request.user) else "ventas:lista",
            "puede_anularse": se_puede_anular(venta),
        },
        status=status,
    )


@requiere_funcion(*VER_VENTAS)
@require_GET
def detalle(request, pk):
    return _detalle(request, _venta_visible(request, pk), AnularVentaForm())


@requiere_funcion("Historial de ventas")
@require_POST
def anular(request, pk):
    """Anula con motivo y revierte caja y stock en el servicio (DEC-45, DEC-66)."""
    if not puede_anular(request.user):
        raise PermissionDenied
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
