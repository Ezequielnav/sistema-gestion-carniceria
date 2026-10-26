from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.caja.forms import AbrirCajaForm, CierreForm, EgresoForm
from apps.caja.models import Caja, EstadoCaja
from apps.caja.services import (
    abrir_caja,
    caja_abierta,
    cerrar_caja,
    detalle_de_cierre,
    egresos_otros,
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
    hoy = timezone.localdate()
    contexto = {"caja": abierta, "form": form, "egreso_form": egreso_form, "egresos": []}
    if abierta is not None:
        contexto["de_otro_dia"] = abierta.fecha != hoy
        contexto["egresos"] = egresos_otros(abierta)
        contexto["egreso_form"] = egreso_form or EgresoForm()
    return render(request, "caja/caja.html", contexto)


@requiere_funcion("Caja")
@require_http_methods(["GET", "POST"])
def caja(request):
    """CU-02: estado de la caja y, si no hay ninguna abierta, el formulario de apertura."""
    _solo_cajera(request)
    abierta = caja_abierta()
    libres = turnos_libres(timezone.localdate())
    form = None
    if abierta is None and libres:
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
    return render(request, "caja/cerrar.html", {"caja": abierta, "form": form})


@login_required
@require_GET
def cierre(request, pk):
    """Reporte de cierre (RF-08): cajera, Administrador y Dueños (DEC-59)."""
    if not puede_ver_cierre(request.user):
        raise PermissionDenied
    caja = get_object_or_404(
        Caja.objects.select_related("usuario", "cerrada_por_usuario"),
        pk=pk,
        estado=EstadoCaja.CERRADA,
    )
    return render(
        request,
        "caja/cierre.html",
        {
            "caja": caja,
            "detalle": detalle_de_cierre(caja),
            "egresos": egresos_otros(caja),
            "es_cajera": puede_abrir(request.user),
        },
    )
