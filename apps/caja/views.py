from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.caja.forms import AbrirCajaForm
from apps.caja.services import abrir_caja, caja_abierta, puede_abrir, turnos_libres
from apps.comun.permisos import requiere_funcion


@requiere_funcion("Caja")
@require_http_methods(["GET", "POST"])
def caja(request):
    """CU-02: estado de la caja y, si no hay ninguna abierta, el formulario de apertura."""
    if not puede_abrir(request.user):
        raise PermissionDenied
    hoy = timezone.localdate()
    abierta = caja_abierta()
    libres = turnos_libres(hoy)
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
    de_otro_dia = abierta is not None and abierta.fecha != hoy
    return render(
        request, "caja/caja.html", {"caja": abierta, "form": form, "de_otro_dia": de_otro_dia}
    )
