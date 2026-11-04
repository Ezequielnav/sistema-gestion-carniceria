from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.caja.forms import AbrirCajaForm, CierreForm, EgresoForm, MedioPagoForm
from apps.caja.models import MedioPago
from apps.caja.services import (
    abrir_caja,
    anulaciones,
    caja_abierta,
    caja_cerrada,
    cambiar_activo,
    cerrar_caja,
    crear_medio,
    detalle_de_cierre,
    egresos_otros,
    es_de_otro_dia,
    listar_medios,
    modificar_medio,
    movimientos_de_cobros,
    movimientos_de_pagos_a_proveedores,
    puede_abrir,
    puede_ver_cierre,
    registrar_egreso_otro,
    resumen_de_cierre,
    turnos_libres,
)
from apps.comun.permisos import requiere_funcion


def _solo_cajera(request):
    if not puede_abrir(request.user):
        raise PermissionDenied


def _pantalla_caja(request, abierta, form=None, egreso_form=None):
    contexto = {"caja": abierta, "form": form, "egreso_form": egreso_form, "egresos": []}
    if abierta is not None:
        contexto["de_otro_dia"] = es_de_otro_dia(abierta)
        contexto["egresos"] = egresos_otros(abierta)
        contexto["egreso_form"] = egreso_form or EgresoForm()
    return render(request, "caja/caja.html", contexto)


@requiere_funcion("Caja")
@require_http_methods(["GET", "POST"])
def caja(request):
    """CU-02: estado de la caja y, si no hay ninguna abierta, el formulario de apertura."""
    _solo_cajera(request)
    abierta = caja_abierta()
    libres = turnos_libres()
    form = None
    if abierta is None:
        form = AbrirCajaForm(request.POST or None, turnos=libres)
        if request.method == "POST" and form.is_valid():
            try:
                nueva = abrir_caja(
                    request.user, form.cleaned_data["turno"], form.cleaned_data["monto_inicial"]
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                turno = nueva.get_turno_display().lower()
                messages.success(request, f"Se abrió la caja del turno {turno}.")
                return redirect("caja:caja")
    return _pantalla_caja(request, abierta, form=form)


@requiere_funcion("Caja")
@require_POST
def egreso(request):
    """SC-02: egreso "otro" en efectivo de la caja abierta (DEC-43)."""
    _solo_cajera(request)
    abierta = caja_abierta()
    if abierta is None:
        messages.info(request, "No hay una caja abierta: el egreso no se registró.")
        return redirect("caja:caja")
    form = EgresoForm(request.POST)
    if form.is_valid():
        try:
            registrar_egreso_otro(
                request.user, form.cleaned_data["monto"], form.cleaned_data["descripcion"]
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Se registró el egreso.")
            return redirect("caja:caja")
    return _pantalla_caja(request, abierta, egreso_form=form)


@requiere_funcion("Caja")
@require_http_methods(["GET", "POST"])
def cerrar(request):
    """CU-03: lo esperado por medio, lo contado y el motivo si hay diferencias."""
    _solo_cajera(request)
    abierta = caja_abierta()
    if abierta is None:
        messages.info(request, "No hay una caja abierta para cerrar.")
        return redirect("caja:caja")
    form = CierreForm(request.POST or None, resumen=resumen_de_cierre(abierta))
    if request.method == "POST" and form.is_valid():
        try:
            cerrada = cerrar_caja(request.user, form.contados(), form.cleaned_data["observacion"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Se cerró la caja.")
            return redirect("caja:cierre", pk=cerrada.pk)
    return render(
        request,
        "caja/cerrar.html",
        {
            "caja": abierta,
            "form": form,
            "anulaciones": anulaciones(abierta),
            "pagos_proveedores": movimientos_de_pagos_a_proveedores(abierta),
            "cobros": movimientos_de_cobros(abierta),
        },
    )


@login_required
@require_GET
def cierre(request, pk):
    """Reporte de cierre (RF-08): cajera, Administrador y Dueños (DEC-59)."""
    if not puede_ver_cierre(request.user):
        raise PermissionDenied
    try:
        caja = caja_cerrada(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error
    return render(
        request,
        "caja/cierre.html",
        {
            "caja": caja,
            "detalle": detalle_de_cierre(caja),
            "egresos": egresos_otros(caja),
            "anulaciones": anulaciones(caja),
            "pagos_proveedores": movimientos_de_pagos_a_proveedores(caja),
            "cobros": movimientos_de_cobros(caja),
            "es_cajera": puede_abrir(request.user),
        },
    )


# Medios de pago (DEC-155, L18): solo el Administrador, sin borrado.


def _medio(pk):
    try:
        return MedioPago.objects.get(pk=pk)
    except MedioPago.DoesNotExist as error:
        raise Http404 from error


@requiere_funcion("Medios de pago")
@require_GET
def medios(request):
    return render(request, "caja/medios.html", {"medios": listar_medios(request.user)})


def _guardar_medio(request, form, operacion, mensaje):
    if request.method == "POST" and form.is_valid():
        try:
            medio = operacion(form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, mensaje.format(medio=medio))
            return redirect("caja:medios")
    return None


@requiere_funcion("Medios de pago")
@require_http_methods(["GET", "POST"])
def medio_nuevo(request):
    form = MedioPagoForm(request.POST or None)
    respuesta = _guardar_medio(
        request,
        form,
        lambda datos: crear_medio(
            request.user, datos["nombre"], datos["ingresa_a_caja"], datos["es_efectivo"]
        ),
        "Se dio de alta el medio de pago «{medio}».",
    )
    return respuesta or render(request, "caja/medio_form.html", {"form": form})


@requiere_funcion("Medios de pago")
@require_http_methods(["GET", "POST"])
def medio_editar(request, pk):
    medio = _medio(pk)
    form = MedioPagoForm(request.POST or None, es_alta=False, initial={"nombre": medio.nombre})
    respuesta = _guardar_medio(
        request,
        form,
        lambda datos: modificar_medio(request.user, medio, datos["nombre"]),
        "Se guardaron los cambios de «{medio}».",
    )
    if respuesta:
        return respuesta
    if request.method == "POST":
        medio.refresh_from_db()
    return render(request, "caja/medio_form.html", {"form": form, "medio": medio})


@requiere_funcion("Medios de pago")
@require_POST
def medio_activo(request, pk):
    """Activa o desactiva según el botón (DEC-155); el efectivo no se desactiva."""
    medio = _medio(pk)
    activo = request.POST.get("activo") == "1"
    try:
        cambiar_activo(request.user, medio, activo)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        estado = "Se activó" if activo else "Se desactivó"
        messages.success(request, f"{estado} el medio de pago «{medio}».")
    return redirect("caja:medios")
