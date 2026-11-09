"""Reglas de CU-11 Gestionar productos, con el stock editable (DEC-98), y servicio de stock."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Count, ExpressionWrapper, F, Q

from apps.catalogo.models import AjusteStock, Categoria, MotivoAjuste, Producto, UnidadMedida
from apps.usuarios.models import Rol

MILESIMA = Decimal("0.001")
# campo_cantidad: 12 dígitos con 3 decimales. El ingreso no tiene el tope de la venta (DEC-76).
CANTIDAD_FUERA_DE_RANGO = Decimal("1000000000")
# Rango de stock_actual, la misma columna: hasta ±999.999.999,999 (L19, DEC-169, DEC-175).
STOCK_MAXIMO = CANTIDAD_FUERA_DE_RANGO - MILESIMA

# Campos que se cargan desde la pantalla. stock_actual no está: el Administrador lo edita
# aparte y el servicio lo cambia con mover_stock y un ajuste registrado (DEC-98, RI-17);
# activo cambia solo con la baja.
CAMPOS_EDITABLES = [
    "nombre",
    "categoria",
    "plus_interno",
    "precio_venta",
    "unidad_medida",
    "controla_stock",
    "stock_minimo",
]


# Stock y cantidades (R-1, R-2): ventas, anulaciones, ingresos y ajustes usan solo estas
# funciones.


def _validar_formato(producto, cantidad, que, entera):
    """Entera por unidad y hasta 3 decimales por kg (DEC-48, DEC-79)."""
    if abs(cantidad) >= CANTIDAD_FUERA_DE_RANGO:
        raise ValidationError(f"{que.capitalize()} de {producto} es demasiado grande.")
    if producto.unidad_medida == UnidadMedida.UNIDAD and cantidad != cantidad.to_integral_value():
        raise ValidationError(f"{producto} se vende por unidad: {que} tiene que ser {entera}.")
    if cantidad != cantidad.quantize(MILESIMA):
        raise ValidationError(f"{que.capitalize()} de {producto} admite hasta 3 decimales.")


def validar_cantidad(producto, cantidad):
    """Mayor a 0 (RI-16); entera por unidad y hasta 3 decimales por kg (DEC-48, DEC-79).

    El tope por línea de la venta (DEC-76) no va acá: lo agrega ventas.
    """
    if cantidad <= 0:
        raise ValidationError(f"La cantidad de {producto} tiene que ser mayor a 0.")
    _validar_formato(producto, cantidad, "la cantidad", "entera")


def validar_stock_contado(producto, cantidad):
    """Stock editado a mano: como validar_cantidad, pero admite 0 (RI-17, DEC-98)."""
    if cantidad < 0:
        raise ValidationError("El stock no puede ser negativo.")
    _validar_formato(producto, cantidad, "el stock", "entero")


def mover_stock(producto, cantidad):
    """Suma `cantidad` al stock (resta si es negativa) si el producto lo controla (RI-07).

    Única forma de cambiar stock_actual (DEC-96). Puede quedar negativo (DEC-46), pero no fuera
    del rango de la columna: ese movimiento se rechaza con un mensaje en lugar del error de la
    base (L19, DEC-169, DEC-175). Se llama dentro de la transacción de la operación que mueve
    el stock, que así no registra nada.
    """
    if not producto.controla_stock:
        return
    # La condición va en el mismo UPDATE: compara con el stock de ese momento.
    movidos = Producto.objects.filter(
        pk=producto.pk,
        stock_actual__lte=STOCK_MAXIMO - cantidad,
        stock_actual__gte=-STOCK_MAXIMO - cantidad,
    ).update(stock_actual=F("stock_actual") + cantidad)
    if not movidos:
        raise ValidationError(
            f"El stock de «{producto.nombre}» quedaría fuera del rango permitido.",
            code="stock_fuera_de_rango",
        )


def cantidad_de_productos_activos():
    return Producto.objects.filter(activo=True).count()


def puede_crear(usuario):
    """RN-05: el Administrador y la cajera con permiso de alta."""
    return usuario.rol == Rol.ADMINISTRADOR or (
        usuario.rol == Rol.CAJERA and usuario.puede_crear_productos
    )


def puede_modificar(usuario):
    """Modificar, dar de baja y cambiar el stock: solo el Administrador (CU-11, RN-05, DEC-103)."""
    return usuario.rol == Rol.ADMINISTRADOR


def puede_ver_stock(usuario):
    """El Administrador y toda cajera, con o sin permiso de alta, en solo lectura (DEC-103)."""
    return usuario.rol in (Rol.ADMINISTRADOR, Rol.CAJERA)


# CU-06: única definición de la alerta de stock (R-8, DEC-82, DEC-101). La carne no lleva
# alerta porque no controla stock (DEC-36) y un producto dado de baja tampoco.
ALERTA_DE_STOCK = Q(activo=True, controla_stock=True) & (
    Q(stock_minimo__isnull=False, stock_actual__lte=F("stock_minimo"))
    | Q(stock_minimo__isnull=True, stock_actual__lte=0)
)


def con_alerta_de_stock(productos):
    """Agrega a cada producto `alerta_stock`, para marcarlo en el listado."""
    return productos.annotate(
        alerta_stock=ExpressionWrapper(ALERTA_DE_STOCK, output_field=BooleanField())
    )


def cantidad_con_stock_bajo():
    """Para la tarjeta "stock bajo" del inicio del Administrador (DEC-30, DEC-82)."""
    return Producto.objects.filter(ALERTA_DE_STOCK).count()


def categorias_para_filtrar():
    return Categoria.objects.order_by("nombre")


def proveedores_para_filtrar():
    """(id, nombre) de los proveedores activos con productos, por la relación inversa de
    `producto_proveedor`: catálogo no importa `proveedores` (R-6, R-7)."""
    return list(
        Producto.objects.filter(productoproveedor__proveedor__activo=True)
        .order_by("productoproveedor__proveedor__nombre")
        .values_list("productoproveedor__proveedor_id", "productoproveedor__proveedor__nombre")
        .distinct()
    )


def buscar_productos(texto="", incluir_inactivos=False):
    """Productos por nombre (contiene) o plus interno (exacto), ordenados por nombre."""
    productos = Producto.objects.select_related("categoria").order_by("nombre", "pk")
    if not incluir_inactivos:
        productos = productos.filter(activo=True)
    texto = texto.strip()
    if texto:
        productos = productos.filter(Q(nombre__icontains=texto) | Q(plus_interno__iexact=texto))
    return productos


def listar_productos(
    usuario,
    texto="",
    pedir_inactivos=False,
    categoria_id=None,
    proveedor_id=None,
    solo_stock_bajo=False,
):
    """Productos de la pantalla, con la consulta de stock de CU-06 (DEC-105).

    Solo el Administrador puede incluir los dados de baja. Devuelve los productos, con su
    alerta de stock, y si se incluyeron los dados de baja.
    """
    incluir_inactivos = pedir_inactivos and puede_modificar(usuario)
    productos = con_alerta_de_stock(buscar_productos(texto, incluir_inactivos))
    if categoria_id is not None:
        productos = productos.filter(categoria_id=categoria_id)
    if proveedor_id is not None:
        productos = productos.filter(productoproveedor__proveedor_id=proveedor_id)
    if solo_stock_bajo:
        productos = productos.filter(ALERTA_DE_STOCK)
    return productos, incluir_inactivos


def producto_editable(pk):
    """Producto activo; uno dado de baja no se edita ni se da de baja otra vez (DEC-33).

    Producto.DoesNotExist si no existe o está dado de baja.
    """
    return Producto.objects.get(pk=pk, activo=True)


def _guardar(producto):
    """Valida y guarda; un plus interno repetido sale como mensaje claro (CU-11, A1)."""
    if producto.plus_interno is not None:
        producto.plus_interno = producto.plus_interno.strip() or None
    producto.full_clean(validate_constraints=False)
    if (
        producto.plus_interno
        and Producto.objects.filter(plus_interno=producto.plus_interno)
        .exclude(pk=producto.pk)
        .exists()
    ):
        raise _plus_repetido(producto.plus_interno)
    try:
        # Savepoint: si otra operación guardó el mismo plus a la vez, la base lo rechaza.
        with transaction.atomic():
            producto.save()
    except IntegrityError as error:
        if "producto_plus_interno_unico" in str(error):
            raise _plus_repetido(producto.plus_interno) from error
        raise
    return producto


def _plus_repetido(plus):
    return ValidationError(
        {"plus_interno": f"Ya existe un producto con el plus interno {plus}."},
        code="plus_repetido",
    )


def _validar_categoria(categoria):
    """Una categoría dada de baja no se asigna; el producto que ya la tiene la conserva
    (DEC-155)."""
    if categoria is not None and not categoria.activo:
        raise ValidationError({"categoria": f"La categoría «{categoria}» está dada de baja."})


def crear_producto(usuario, datos, stock=None):
    """Alta de producto. El nombre repetido no se bloquea (propuesta no confirmada de CU-11).

    El stock es solo del Administrador; si es mayor a 0 se registra como ajuste
    "Stock inicial" (DEC-99). La cajera con permiso de alta arranca en 0 (DEC-103).
    """
    if not puede_crear(usuario):
        raise PermissionDenied("Tu usuario no tiene permiso para dar de alta productos.")
    if stock and not puede_modificar(usuario):
        raise PermissionDenied("Solo el administrador carga el stock.")
    producto = Producto(**{campo: datos.get(campo) for campo in CAMPOS_EDITABLES})
    _validar_categoria(producto.categoria)
    producto.stock_actual = 0
    if stock:
        validar_stock_editado(producto, stock)
    with transaction.atomic():
        _guardar(producto)
        if stock:
            _registrar_ajuste(usuario, producto, stock, MotivoAjuste.STOCK_INICIAL)
    return producto


def modificar_producto(usuario, producto, datos, stock=None, stock_mostrado=None, motivo=None):
    """Modifica el producto y, si el Administrador cambió el stock, registra el ajuste (DEC-98).

    El cambio se mide contra el stock que mostró el formulario (`stock_mostrado`), no contra
    el actual: una venta hecha mientras se editaba no se deshace por error.
    """
    if not puede_modificar(usuario):
        raise PermissionDenied("Solo el administrador puede modificar productos.")
    if datos.get("categoria") is not None and datos["categoria"].pk != producto.categoria_id:
        _validar_categoria(datos["categoria"])
    for campo in CAMPOS_EDITABLES:
        setattr(producto, campo, datos.get(campo))
    cambia_stock = stock_cambiado(producto, stock, stock_mostrado)
    if cambia_stock:
        validar_stock_editado(producto, stock)
    with transaction.atomic():
        _guardar(producto)
        if cambia_stock:
            _registrar_ajuste(usuario, producto, stock, motivo or MotivoAjuste.MODIFICACION_MANUAL)
    return producto


def dar_de_baja(usuario, producto):
    """Baja lógica: el producto queda inactivo y sus ventas e ingresos no cambian (RI-11)."""
    if not puede_modificar(usuario):
        raise PermissionDenied("Solo el administrador puede dar de baja productos.")
    producto.activo = False
    producto.save(update_fields=["activo", "actualizado_en"])
    return producto


def producto_dado_de_baja(pk):
    """Producto inactivo, para reactivarlo (DEC-85). Producto.DoesNotExist si no lo es."""
    return Producto.objects.get(pk=pk, activo=False)


def reactivar(usuario, producto):
    """Vuelve a activar un producto dado de baja, sin condición de stock (DEC-85)."""
    if not puede_modificar(usuario):
        raise PermissionDenied("Solo el administrador puede reactivar productos.")
    producto.activo = True
    producto.save(update_fields=["activo", "actualizado_en"])
    return producto


# Stock editado a mano al crear o modificar (DEC-98, supuesto del proyecto)

MOTIVOS_DE_MODIFICACION = [m for m in MotivoAjuste if m != MotivoAjuste.STOCK_INICIAL]


def stock_cambiado(producto, stock, stock_mostrado=None):
    """Si hay que registrar un ajuste: el stock enviado difiere del que se mostró."""
    if stock is None:
        return False
    referencia = producto.stock_actual if stock_mostrado is None else stock_mostrado
    return stock != referencia


def validar_stock_editado(producto, stock):
    """Solo con control de stock; mayor o igual a 0 y con el formato de DEC-79 (RI-17).

    `producto` lleva la unidad y el control de stock que se están guardando.
    """
    if not producto.controla_stock:
        raise ValidationError({"stock": "Solo los productos que controlan stock tienen stock."})
    try:
        validar_stock_contado(producto, stock)
    except ValidationError as error:
        raise ValidationError({"stock": error.messages}) from error


def _registrar_ajuste(usuario, producto, stock_nuevo, motivo):
    """Lleva el stock al valor indicado con mover_stock y guarda el ajuste (RI-07, RI-17).

    Se llama dentro de una transacción; bloquea el producto para que el stock anterior sea
    el del momento aunque haya ventas al mismo tiempo.
    """
    anterior = Producto.objects.select_for_update().get(pk=producto.pk).stock_actual
    mover_stock(producto, stock_nuevo - anterior)
    producto.stock_actual = stock_nuevo
    return AjusteStock.objects.create(
        producto=producto,
        usuario=usuario,
        stock_anterior=anterior,
        stock_nuevo=stock_nuevo,
        motivo=motivo,
    )


# Categorías y consulta de ajustes de stock, solo del Administrador (DEC-155, L18).


def _exigir_administrador(usuario):
    if not puede_modificar(usuario):
        raise PermissionDenied("Solo el administrador gestiona el catálogo.")


def listar_categorias(usuario, incluir_inactivas=False):
    _exigir_administrador(usuario)
    categorias = Categoria.objects.order_by("nombre", "pk")
    return categorias if incluir_inactivas else categorias.filter(activo=True)


def categoria_editable(pk):
    """Categoría activa; una dada de baja primero se reactiva. Categoria.DoesNotExist si no."""
    return Categoria.objects.get(pk=pk, activo=True)


def categoria_dada_de_baja(pk):
    return Categoria.objects.get(pk=pk, activo=False)


def _guardar_categoria(categoria, nombre):
    categoria.nombre = (nombre or "").strip()
    # El nombre es único sin distinguir mayúsculas (DEC-31); full_clean da el mensaje.
    categoria.full_clean()
    categoria.save()
    return categoria


def crear_categoria(usuario, nombre):
    _exigir_administrador(usuario)
    return _guardar_categoria(Categoria(), nombre)


def modificar_categoria(usuario, categoria, nombre):
    _exigir_administrador(usuario)
    return _guardar_categoria(categoria, nombre)


def dar_de_baja_categoria(usuario, categoria):
    """Baja lógica: los productos que la tienen la conservan (DEC-155, RI-11)."""
    _exigir_administrador(usuario)
    categoria.activo = False
    categoria.save(update_fields=["activo", "actualizado_en"])
    return categoria


def reactivar_categoria(usuario, categoria):
    _exigir_administrador(usuario)
    categoria.activo = True
    categoria.save(update_fields=["activo", "actualizado_en"])
    return categoria


def productos_por_categoria(ids):
    """Cantidad de productos de cada categoría, en una sola consulta: {id: cantidad}."""
    filas = (
        Producto.objects.filter(categoria_id__in=ids)
        .values("categoria_id")
        .annotate(cantidad=Count("pk"))
    )
    return {fila["categoria_id"]: fila["cantidad"] for fila in filas}


def listar_ajustes(usuario, desde=None, hasta=None, producto=None):
    """Ajustes de stock, más nuevos primero, en solo lectura (DEC-155, RI-17)."""
    _exigir_administrador(usuario)
    ajustes = AjusteStock.objects.select_related("producto", "usuario").order_by(
        "-fecha_hora", "-pk"
    )
    if desde:
        ajustes = ajustes.filter(fecha_hora__date__gte=desde)
    if hasta:
        ajustes = ajustes.filter(fecha_hora__date__lte=hasta)
    if producto:
        ajustes = ajustes.filter(producto=producto)
    return ajustes


def productos_con_ajustes():
    """Para el filtro: solo los productos que tienen algún ajuste."""
    return Producto.objects.filter(ajustestock__isnull=False).distinct().order_by("nombre", "pk")
