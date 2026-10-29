from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.comun.permisos import requiere_funcion
from apps.proveedores.forms import ProveedorForm
from apps.proveedores.services import (
    CAMPOS_EDITABLES,
    crear_proveedor,
    dar_de_baja,
    listar_proveedores,
    modificar_proveedor,
    proveedor_dado_de_baja,
    proveedor_editable,
    reactivar,
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
