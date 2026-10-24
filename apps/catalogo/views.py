from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.catalogo.forms import ProductoForm
from apps.catalogo.models import Producto
from apps.catalogo.services import (
    CAMPOS_EDITABLES,
    buscar_productos,
    crear_producto,
    dar_de_baja,
    modificar_producto,
    puede_crear,
    puede_modificar,
)
from apps.comun.permisos import requiere_funcion

POR_PAGINA = 25


@requiere_funcion("Productos")
def productos(request):
    es_admin = puede_modificar(request.user)
    texto = request.GET.get("q", "").strip()
    # Solo el Administrador puede ver los dados de baja.
    incluir_inactivos = es_admin and request.GET.get("inactivos") == "1"
    pagina = Paginator(buscar_productos(texto, incluir_inactivos), POR_PAGINA).get_page(
        request.GET.get("pagina")
    )
    return render(
        request,
        "catalogo/productos.html",
        {
            "pagina": pagina,
            "texto": texto,
            "incluir_inactivos": incluir_inactivos,
            "puede_crear": puede_crear(request.user),
            "puede_modificar": es_admin,
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
    producto = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, initial=model_to_dict(producto, CAMPOS_EDITABLES))
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: modificar_producto(request.user, producto, datos),
        "Se guardaron los cambios de «{producto}».",
    )
    return respuesta or render(
        request, "catalogo/producto_form.html", {"form": form, "producto": producto}
    )


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def baja(request, pk):
    if not puede_modificar(request.user):
        raise PermissionDenied
    producto = get_object_or_404(Producto, pk=pk, activo=True)
    if request.method == "POST":
        dar_de_baja(request.user, producto)
        messages.success(request, f"Se dio de baja «{producto}».")
        return redirect("catalogo:productos")
    return render(request, "catalogo/producto_baja.html", {"producto": producto})
