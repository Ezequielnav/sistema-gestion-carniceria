from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.caja.services import efectivo_disponible, egreso_de_pago
from apps.catalogo.forms import ProductoForm
from apps.catalogo.services import crear_producto
from apps.comun.models import subtotal
from apps.comun.permisos import requiere_funcion
from apps.proveedores.forms import (
    AnularIngresoForm,
    AnularPagoForm,
    ConfirmarIngresoForm,
    PagoForm,
    ProveedorForm,
)
from apps.proveedores.services import (
    CAMPOS_EDITABLES,
    anular_ingreso,
    anular_pago,
    buscar_para_ingreso,
    crear_proveedor,
    dar_de_baja,
    impedimento_para_anular,
    impedimento_para_anular_pago,
    ingreso_con_detalles,
    listar_ingresos,
    listar_pagos,
    listar_proveedores,
    modificar_proveedor,
    pago_con_detalles,
    precios_sugeridos,
    proveedor_dado_de_baja,
    proveedor_editable,
    reactivar,
    registrar_ingreso,
    registrar_pago,
    saldo_de_ingreso,
    saldos_de_proveedores,
)

# DEC-95: de a 25, como productos y el historial de ventas.
POR_PAGINA = 25


def _buscar(funcion, pk):
    try:
        return funcion(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error


@requiere_funcion("Proveedores")
def proveedores(request):
    """CU-13: listado de activos; "Incluir dados de baja" suma los inactivos (DEC-87)."""
    texto = request.GET.get("q", "").strip()
    incluir_inactivos = request.GET.get("inactivos") == "1"
    lista = listar_proveedores(request.user, texto, incluir_inactivos)
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    # Saldo derivado: ingresos vigentes menos pagos (DEC-81), no se guarda.
    saldos = saldos_de_proveedores(pagina.object_list)
    for proveedor in pagina.object_list:
        proveedor.saldo = saldos[proveedor.pk]
    return render(
        request,
        "proveedores/proveedores.html",
        {"pagina": pagina, "texto": texto, "incluir_inactivos": incluir_inactivos},
    )


def _guardar_con(request, form, operacion, mensaje):
    """Llama al servicio y pasa sus errores al formulario, junto al campo que corresponde."""
    if request.method == "POST" and form.is_valid():
        try:
            proveedor = operacion(form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, mensaje.format(proveedor=proveedor))
            return redirect("proveedores:proveedores")
    return None


@requiere_funcion("Proveedores")
@require_http_methods(["GET", "POST"])
def nuevo(request):
    form = ProveedorForm(request.POST or None)
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: crear_proveedor(request.user, datos),
        "Se dio de alta «{proveedor}».",
    )
    return respuesta or render(request, "proveedores/proveedor_form.html", {"form": form})


@requiere_funcion("Proveedores")
@require_http_methods(["GET", "POST"])
def editar(request, pk):
    # Un proveedor dado de baja no se edita: primero se reactiva (DEC-87).
    proveedor = _buscar(proveedor_editable, pk)
    form = ProveedorForm(request.POST or None, initial=model_to_dict(proveedor, CAMPOS_EDITABLES))
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: modificar_proveedor(request.user, proveedor, datos),
        "Se guardaron los cambios de «{proveedor}».",
    )
    if respuesta:
        return respuesta
    if request.method == "POST":
        # Si el servicio rechazó los datos, el título vuelve a mostrar lo guardado.
        proveedor.refresh_from_db()
    return render(
        request, "proveedores/proveedor_form.html", {"form": form, "proveedor": proveedor}
    )


@requiere_funcion("Proveedores")
@require_http_methods(["GET", "POST"])
def baja(request, pk):
    proveedor = _buscar(proveedor_editable, pk)
    if request.method == "POST":
        dar_de_baja(request.user, proveedor)
        messages.success(request, f"Se dio de baja «{proveedor}».")
        return redirect("proveedores:proveedores")
    return render(request, "proveedores/proveedor_baja.html", {"proveedor": proveedor})


@requiere_funcion("Proveedores")
@require_POST
def reactivar_proveedor(request, pk):
    """Reactiva un proveedor dado de baja desde el listado de inactivos (DEC-87)."""
    proveedor = _buscar(proveedor_dado_de_baja, pk)
    reactivar(request.user, proveedor)
    messages.success(request, f"Se reactivó «{proveedor}».")
    return redirect("proveedores:proveedores")


# CU-05 Registrar ingreso de mercadería, a crédito (DEC-81, DEC-89 a DEC-94)


def _producto(producto, precio):
    return {
        "id": producto.pk,
        "nombre": producto.nombre,
        "plus": producto.plus_interno or "",
        "unidad": producto.unidad_medida,
        "controla_stock": producto.controla_stock,
        # DEC-90: último precio de compra con ese proveedor, si hay.
        "precio": "" if precio is None else str(precio),
    }


@requiere_funcion("Proveedores")
@require_GET
def ingresos(request):
    lista = listar_ingresos(request.user)
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    for ingreso in pagina.object_list:
        ingreso.saldo = saldo_de_ingreso(ingreso)
    return render(request, "proveedores/ingresos.html", {"pagina": pagina})


@requiere_funcion("Proveedores")
@require_GET
def ingreso_nuevo(request):
    return render(
        request,
        "proveedores/ingreso_nuevo.html",
        {"form": ConfirmarIngresoForm(), "form_producto": ProductoForm(prefix="producto")},
    )


@requiere_funcion("Proveedores")
@require_GET
def ingreso_buscar(request):
    """Productos activos con el precio sugerido para el proveedor elegido (DEC-90).

    Con `ids`, solo los precios de esos productos: al cambiar de proveedor se completan otra vez.
    """
    proveedor = request.GET.get("proveedor", "")
    proveedor = int(proveedor) if proveedor.isdigit() else None
    if "ids" in request.GET:
        ids = [int(i) for i in request.GET["ids"].split(",") if i.isdigit()]
        precios = precios_sugeridos(request.user, proveedor, ids)
        return JsonResponse({"precios": {str(k): str(v) for k, v in precios.items()}})
    resultados, hay_mas = buscar_para_ingreso(request.user, request.GET.get("q", ""), proveedor)
    return JsonResponse(
        {"resultados": [_producto(p, precio) for p, precio in resultados], "hay_mas": hay_mas}
    )


@requiere_funcion("Proveedores")
@require_POST
def ingreso_producto(request):
    """CU-05 A1: alta de producto desde el ingreso con el servicio de CU-11 (DEC-91)."""
    form = ProductoForm(request.POST, prefix="producto")
    if form.is_valid():
        try:
            producto = crear_producto(request.user, form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return JsonResponse({"producto": _producto(producto, None)})
    errores = {campo: list(lista) for campo, lista in form.errors.items()}
    return JsonResponse({"errores": errores}, status=400)


@requiere_funcion("Proveedores")
@require_POST
def ingreso_confirmar(request):
    form = ConfirmarIngresoForm(request.POST)
    if not form.is_valid():
        errores = [e for lista in form.errors.values() for e in lista]
        return JsonResponse({"errores": errores}, status=400)
    datos = form.cleaned_data
    try:
        ingreso = registrar_ingreso(
            request.user,
            datos["proveedor"],
            datos["lineas"],
            datos["observacion"],
            datos["condicion_pago"],
            datos["medio_pago"],
        )
    except ValidationError as error:
        return JsonResponse({"errores": error.messages}, status=400)
    messages.success(request, f"Se registró el ingreso N.º {ingreso.pk}.")
    return JsonResponse({"detalle": reverse("proveedores:ingreso", args=[ingreso.pk])})


def _detalle_ingreso(request, ingreso, form, status=200):
    detalles = list(ingreso.detalleingreso_set.select_related("producto").order_by("pk"))
    for detalle in detalles:
        detalle.subtotal = subtotal(detalle.cantidad, detalle.precio_unitario)
    return render(
        request,
        "proveedores/ingreso_detalle.html",
        {
            "ingreso": ingreso,
            "detalles": detalles,
            "pagos": ingreso.pagoproveedor_set.select_related("medio_pago").order_by("pk"),
            "saldo": saldo_de_ingreso(ingreso),
            "impedimento": impedimento_para_anular(ingreso),
            "form": form,
        },
        status=status,
    )


@requiere_funcion("Proveedores")
@require_GET
def ingreso(request, pk):
    ingreso = _buscar(lambda clave: ingreso_con_detalles(request.user, clave), pk)
    return _detalle_ingreso(request, ingreso, AnularIngresoForm())


@requiere_funcion("Proveedores")
@require_POST
def ingreso_anular(request, pk):
    """Anula con motivo, solo sin pagos vigentes; devuelve el stock (DEC-92)."""
    ingreso = _buscar(lambda clave: ingreso_con_detalles(request.user, clave), pk)
    form = AnularIngresoForm(request.POST)
    if form.is_valid():
        try:
            anular_ingreso(request.user, ingreso, form.cleaned_data["motivo"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Se anuló el ingreso N.º {ingreso.pk}.")
            return redirect("proveedores:ingreso", pk=ingreso.pk)
    return _detalle_ingreso(request, ingreso, form, status=400)


# CU-07 Registrar pago a proveedor (DEC-80, DEC-81, DEC-92)


@requiere_funcion("Proveedores")
@require_GET
def pagos(request):
    lista = listar_pagos(request.user)
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(request, "proveedores/pagos.html", {"pagina": pagina})


@requiere_funcion("Proveedores")
@require_http_methods(["GET", "POST"])
def pago_nuevo(request):
    inicial = {}
    if request.method == "GET" and request.GET.get("ingreso", "").isdigit():
        try:
            ingreso = ingreso_con_detalles(request.user, int(request.GET["ingreso"]))
        except ObjectDoesNotExist:
            ingreso = None
        if ingreso is not None:
            inicial = {"ingreso": ingreso.pk, "monto": saldo_de_ingreso(ingreso)}
    form = PagoForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        try:
            pago = registrar_pago(
                request.user, datos["ingreso"], datos["monto"], datos["medio_pago"]
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Se registró el pago N.º {pago.pk}.")
            return redirect("proveedores:pago", pk=pago.pk)
    return render(
        request,
        "proveedores/pago_form.html",
        {"form": form, "efectivo_disponible": efectivo_disponible()},
    )


def _detalle_pago(request, pago, form, status=200):
    return render(
        request,
        "proveedores/pago_detalle.html",
        {
            "pago": pago,
            "egreso": egreso_de_pago(pago),
            "impedimento": impedimento_para_anular_pago(pago),
            "form": form,
        },
        status=status,
    )


@requiere_funcion("Proveedores")
@require_GET
def pago(request, pk):
    pago = _buscar(lambda clave: pago_con_detalles(request.user, clave), pk)
    return _detalle_pago(request, pago, AnularPagoForm())


@requiere_funcion("Proveedores")
@require_POST
def pago_anular(request, pk):
    """Por transferencia, siempre; en efectivo, con la caja del egreso abierta (DEC-92)."""
    pago = _buscar(lambda clave: pago_con_detalles(request.user, clave), pk)
    form = AnularPagoForm(request.POST)
    if form.is_valid():
        try:
            anular_pago(request.user, pago, form.cleaned_data["motivo"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Se anuló el pago N.º {pago.pk}.")
            return redirect("proveedores:pago", pk=pago.pk)
    return _detalle_pago(request, pago, form, status=400)
