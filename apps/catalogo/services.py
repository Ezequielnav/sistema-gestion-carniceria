"""Reglas de CU-11 Gestionar productos."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.catalogo.models import Producto
from apps.usuarios.models import Rol

# Campos que se cargan desde la pantalla. stock_actual no está: arranca en 0 y lo cambian
# solo las ventas y los ingresos (RI-07); activo cambia solo con la baja.
CAMPOS_EDITABLES = [
    "nombre",
    "categoria",
    "plus_interno",
    "precio_venta",
    "unidad_medida",
    "controla_stock",
    "stock_minimo",
]


def cantidad_de_productos_activos():
    return Producto.objects.filter(activo=True).count()


def puede_crear(usuario):
    """RN-05: el Administrador y la cajera con permiso de alta."""
    return usuario.rol == Rol.ADMINISTRADOR or (
        usuario.rol == Rol.CAJERA and usuario.puede_crear_productos
    )


def puede_modificar(usuario):
    """Modificar y dar de baja: solo el Administrador (CU-11, RN-05)."""
    return usuario.rol == Rol.ADMINISTRADOR


def buscar_productos(texto="", incluir_inactivos=False):
    """Productos por nombre (contiene) o plus interno (exacto), ordenados por nombre."""
    productos = Producto.objects.select_related("categoria").order_by("nombre", "pk")
    if not incluir_inactivos:
        productos = productos.filter(activo=True)
    texto = texto.strip()
    if texto:
        productos = productos.filter(Q(nombre__icontains=texto) | Q(plus_interno__iexact=texto))
    return productos


def listar_productos(usuario, texto="", pedir_inactivos=False):
    """Productos de la pantalla; solo el Administrador puede incluir los dados de baja.

    Devuelve los productos y si se incluyeron los dados de baja.
    """
    incluir_inactivos = pedir_inactivos and puede_modificar(usuario)
    return buscar_productos(texto, incluir_inactivos), incluir_inactivos


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


def crear_producto(usuario, datos):
    """Alta de producto. El nombre repetido no se bloquea (propuesta no confirmada de CU-11)."""
    if not puede_crear(usuario):
        raise PermissionDenied("Tu usuario no tiene permiso para dar de alta productos.")
    producto = Producto(**{campo: datos.get(campo) for campo in CAMPOS_EDITABLES})
    producto.stock_actual = 0
    return _guardar(producto)


def modificar_producto(usuario, producto, datos):
    if not puede_modificar(usuario):
        raise PermissionDenied("Solo el administrador puede modificar productos.")
    for campo in CAMPOS_EDITABLES:
        setattr(producto, campo, datos.get(campo))
    return _guardar(producto)


def dar_de_baja(usuario, producto):
    """Baja lógica: el producto queda inactivo y sus ventas e ingresos no cambian (RI-11)."""
    if not puede_modificar(usuario):
        raise PermissionDenied("Solo el administrador puede dar de baja productos.")
    producto.activo = False
    producto.save(update_fields=["activo", "actualizado_en"])
    return producto
