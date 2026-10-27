from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.catalogo.forms import ProductoForm
from apps.catalogo.services import (
    CAMPOS_EDITABLES,
    crear_producto,
    dar_de_baja,
    listar_productos,
    modificar_producto,
    producto_editable,
    puede_crear,
    puede_modificar,
)
from apps.comun.permisos import requiere_funcion

POR_PAGINA = 25


def _producto_editable(pk):
    try:
        return producto_editable(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error


@requiere_funcion("Productos")
def productos(request):
    texto = request.GET.get("q", "").strip()
    productos, incluir_inactivos = listar_productos(
        request.user, texto, pedir_inactivos=request.GET.get("inactivos") == "1"
    )
    pagina = Paginator(productos, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "catalogo/productos.html",
        {
            "pagina": pagina,
            "texto": texto,
            "incluir_inactivos": incluir_inactivos,
            "puede_crear": puede_crear(request.user),
            "puede_modificar": puede_modificar(request.user),
        },
    )


def _guardar_con(request, form, operacion, mensaje):
    """Llama al servicio y pasa sus errores al formulario, junto al campo que corresponde."""
    if request.method == "POST" and form.is_valid():
        try:
            producto = operacion(form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, mensaje.format(producto=producto))
            return redirect("catalogo:productos")
    return None


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def nuevo(request):
    if not puede_crear(request.user):
        raise PermissionDenied
    form = ProductoForm(request.POST or None)
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: crear_producto(request.user, datos),
        "Se dio de alta «{producto}».",
    )
    return respuesta or render(request, "catalogo/producto_form.html", {"form": form})


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def editar(request, pk):
    if not puede_modificar(request.user):
        raise PermissionDenied
    # Un producto dado de baja se reactiva solo desde el panel (DEC-33).
    producto = _producto_editable(pk)
    form = ProductoForm(request.POST or None, initial=model_to_dict(producto, CAMPOS_EDITABLES))
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: modificar_producto(request.user, producto, datos),
        "Se guardaron los cambios de «{producto}».",
    )
    if respuesta:
        return respuesta
    if request.method == "POST":
        # Si el servicio rechazó los datos, el título vuelve a mostrar lo guardado.
        producto.refresh_from_db()
    return render(request, "catalogo/producto_form.html", {"form": form, "producto": producto})


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def baja(request, pk):
    if not puede_modificar(request.user):
        raise PermissionDenied
    producto = _producto_editable(pk)
    if request.method == "POST":
        dar_de_baja(request.user, producto)
        messages.success(request, f"Se dio de baja «{producto}».")
        return redirect("catalogo:productos")
    return render(request, "catalogo/producto_baja.html", {"producto": producto})
