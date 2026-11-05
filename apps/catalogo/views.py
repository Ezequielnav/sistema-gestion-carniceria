from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.catalogo.forms import CategoriaForm, FiltroAjustesForm, ProductoForm
from apps.catalogo.models import cantidad_para_editar
from apps.catalogo.services import (
    CAMPOS_EDITABLES,
    categoria_dada_de_baja,
    categoria_editable,
    categorias_para_filtrar,
    crear_categoria,
    crear_producto,
    dar_de_baja,
    dar_de_baja_categoria,
    listar_ajustes,
    listar_categorias,
    listar_productos,
    modificar_categoria,
    modificar_producto,
    producto_dado_de_baja,
    producto_editable,
    productos_con_ajustes,
    productos_por_categoria,
    proveedores_para_filtrar,
    puede_crear,
    puede_modificar,
    puede_ver_stock,
    reactivar,
    reactivar_categoria,
)
from apps.comun.listados import filtrar_y_paginar
from apps.comun.permisos import requiere_funcion

POR_PAGINA = 25


def _producto_editable(pk):
    try:
        return producto_editable(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error


def _id_de(request, nombre):
    valor = request.GET.get(nombre, "")
    return int(valor) if valor.isdecimal() else None


@requiere_funcion("Productos")
def productos(request):
    """CU-11 y consulta de stock de CU-06 en una sola pantalla (DEC-105)."""
    texto = request.GET.get("q", "").strip()
    categoria = _id_de(request, "categoria")
    proveedor = _id_de(request, "proveedor")
    solo_stock_bajo = request.GET.get("stock_bajo") == "1"
    productos, incluir_inactivos = listar_productos(
        request.user,
        texto,
        pedir_inactivos=request.GET.get("inactivos") == "1",
        categoria_id=categoria,
        proveedor_id=proveedor,
        solo_stock_bajo=solo_stock_bajo,
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
            "ver_stock": puede_ver_stock(request.user),
            "categorias": categorias_para_filtrar(),
            "proveedores": proveedores_para_filtrar(),
            "categoria": categoria,
            "proveedor": proveedor,
            "solo_stock_bajo": solo_stock_bajo,
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
    # DEC-99: el stock inicial es solo del Administrador; la cajera arranca en 0 (DEC-103).
    form = ProductoForm(request.POST or None, con_stock=puede_modificar(request.user))
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: crear_producto(request.user, datos, datos.get("stock")),
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
    inicial = model_to_dict(producto, CAMPOS_EDITABLES)
    # Por unidad, stock y mínimo se muestran enteros ("7", no "7,000"; DEC-48).
    stock = cantidad_para_editar(producto.stock_actual, producto.unidad_medida)
    minimo = cantidad_para_editar(producto.stock_minimo, producto.unidad_medida)
    inicial.update(stock=stock, stock_mostrado=stock, stock_minimo=minimo)
    form = ProductoForm(request.POST or None, initial=inicial, con_stock=True, es_alta=False)
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: modificar_producto(
            request.user,
            producto,
            datos,
            stock=datos.get("stock"),
            stock_mostrado=datos.get("stock_mostrado"),
            motivo=datos.get("motivo_ajuste") or None,
        ),
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


# Categorías y ajustes de stock (DEC-155, L18): solo el Administrador, como modificar
# productos. La vista y el servicio controlan el permiso.


def _solo_administrador(request):
    if not puede_modificar(request.user):
        raise PermissionDenied


def _categoria(funcion, pk):
    try:
        return funcion(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error


@requiere_funcion("Productos")
@require_GET
def categorias(request):
    _solo_administrador(request)
    incluir_inactivas = request.GET.get("inactivas") == "1"
    lista = list(listar_categorias(request.user, incluir_inactivas))
    cantidades = productos_por_categoria([c.pk for c in lista])
    for categoria in lista:
        categoria.productos = cantidades.get(categoria.pk, 0)
    return render(
        request,
        "catalogo/categorias.html",
        {"categorias": lista, "incluir_inactivas": incluir_inactivas},
    )


def _guardar_categoria(request, form, operacion, mensaje):
    if request.method == "POST" and form.is_valid():
        try:
            categoria = operacion(form.cleaned_data["nombre"])
        except ValidationError as error:
            # El único dato es el nombre: el error de nombre repetido va junto al campo.
            form.add_error("nombre", error.messages)
        else:
            messages.success(request, mensaje.format(categoria=categoria))
            return redirect("catalogo:categorias")
    return None


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def categoria_nueva(request):
    _solo_administrador(request)
    form = CategoriaForm(request.POST or None)
    respuesta = _guardar_categoria(
        request,
        form,
        lambda nombre: crear_categoria(request.user, nombre),
        "Se dio de alta la categoría «{categoria}».",
    )
    return respuesta or render(request, "catalogo/categoria_form.html", {"form": form})


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def categoria_editar(request, pk):
    _solo_administrador(request)
    categoria = _categoria(categoria_editable, pk)
    form = CategoriaForm(request.POST or None, initial={"nombre": categoria.nombre})
    respuesta = _guardar_categoria(
        request,
        form,
        lambda nombre: modificar_categoria(request.user, categoria, nombre),
        "Se guardaron los cambios de «{categoria}».",
    )
    if respuesta:
        return respuesta
    if request.method == "POST":
        categoria.refresh_from_db()
    return render(request, "catalogo/categoria_form.html", {"form": form, "categoria": categoria})


@requiere_funcion("Productos")
@require_http_methods(["GET", "POST"])
def categoria_baja(request, pk):
    _solo_administrador(request)
    categoria = _categoria(categoria_editable, pk)
    if request.method == "POST":
        dar_de_baja_categoria(request.user, categoria)
        messages.success(request, f"Se dio de baja la categoría «{categoria}».")
        return redirect("catalogo:categorias")
    cantidad = productos_por_categoria([categoria.pk]).get(categoria.pk, 0)
    return render(
        request, "catalogo/categoria_baja.html", {"categoria": categoria, "productos": cantidad}
    )


@requiere_funcion("Productos")
@require_POST
def categoria_reactivar(request, pk):
    _solo_administrador(request)
    categoria = _categoria(categoria_dada_de_baja, pk)
    reactivar_categoria(request.user, categoria)
    messages.success(request, f"Se reactivó la categoría «{categoria}».")
    return redirect("catalogo:categorias")


@requiere_funcion("Productos")
@require_GET
def ajustes(request):
    """Consulta de ajustes de stock, de solo lectura (DEC-155, RI-17)."""
    _solo_administrador(request)
    form = FiltroAjustesForm(request.GET or None, productos=productos_con_ajustes())
    pagina, filtros = filtrar_y_paginar(
        request,
        form,
        lambda datos: listar_ajustes(
            request.user, datos.get("desde"), datos.get("hasta"), datos.get("producto")
        ),
    )
    return render(
        request, "catalogo/ajustes.html", {"form": form, "pagina": pagina, "filtros": filtros}
    )
