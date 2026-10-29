from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalogo.forms import AjusteStockForm, ProductoForm
from apps.catalogo.models import formatear_cantidad
from apps.catalogo.services import (
    CAMPOS_EDITABLES,
    ajustar_stock,
    crear_producto,
    dar_de_baja,
    listar_productos,
    modificar_producto,
    producto_ajustable,
    producto_dado_de_baja,
    producto_editable,
    puede_crear,
    puede_modificar,
    reactivar,
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
    # DEC-99: el stock inicial es solo del Administrador.
    form = ProductoForm(request.POST or None, con_stock_inicial=puede_modificar(request.user))
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: crear_producto(request.user, datos, datos.get("stock_inicial")),
        "Se dio de alta «{producto}».",
    )
    return respuesta or render(request, "catalogo/producto_form.html", {"form": form})


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def editar(request, pk):
    if not puede_modificar(request.user):
        raise PermissionDenied
    # Un producto dado de baja no se edita: primero se reactiva (DEC-33, DEC-85).
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


@requiere_funcion("Productos")
@require_POST
def reactivar_producto(request, pk):
    """Reactiva un producto dado de baja desde el listado de inactivos (DEC-85)."""
    if not puede_modificar(request.user):
        raise PermissionDenied
    try:
        producto = producto_dado_de_baja(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error
    reactivar(request.user, producto)
    messages.success(request, f"Se reactivó «{producto}».")
    return redirect("catalogo:productos")


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def ajustar(request, pk):
    """CU-15: stock contado y motivo; queda registrado (DEC-98)."""
    if not puede_modificar(request.user):
        raise PermissionDenied
    try:
        producto = producto_ajustable(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error
    form = AjusteStockForm(request.POST or None, producto=producto)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        try:
            ajuste = ajustar_stock(
                request.user,
                producto,
                datos["stock_contado"],
                datos["motivo"],
                datos["observacion"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request,
                f"Se ajustó el stock de «{producto}»: "
                f"{formatear_cantidad(ajuste.stock_nuevo, producto.unidad_medida)}.",
            )
            return redirect("catalogo:productos")
    return render(request, "catalogo/ajuste_form.html", {"form": form, "producto": producto})
