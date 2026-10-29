"""Reglas de CU-13 Gestionar proveedores (DEC-87, DEC-88) y CU-05 ingreso de mercadería.

Mismo patrón que CU-11: alta, modificación, baja lógica y reactivación, solo del
Administrador. El nombre repetido no se bloquea (DEC-87). R-6: este módulo puede usar
catálogo y caja, pero ellos nunca importan `proveedores`.
"""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.catalogo.services import buscar_productos, mover_stock, validar_cantidad
from apps.comun.models import subtotal
from apps.proveedores.models import (
    CondicionPago,
    DetalleIngreso,
    EstadoIngreso,
    IngresoMercaderia,
    PagoProveedor,
    ProductoProveedor,
    Proveedor,
)
from apps.usuarios.models import Rol

# Datos de contacto a confirmar (PR-31).
CAMPOS_EDITABLES = ["nombre", "telefono", "email"]


def puede_gestionar(usuario):
    """CU-13 es solo del Administrador (DEC-88); permiso doble con la vista (R-9)."""
    return usuario.rol == Rol.ADMINISTRADOR


def _exigir_permiso(usuario):
    if not puede_gestionar(usuario):
        raise PermissionDenied("Solo el administrador gestiona proveedores.")


def listar_proveedores(usuario, texto="", incluir_inactivos=False):
    """Por nombre, teléfono o email (contiene), ordenados por nombre; los dados de baja solo
    si se piden (DEC-87)."""
    _exigir_permiso(usuario)
    proveedores = Proveedor.objects.order_by("nombre", "pk")
    if not incluir_inactivos:
        proveedores = proveedores.filter(activo=True)
    texto = texto.strip()
    if texto:
        proveedores = proveedores.filter(
            Q(nombre__icontains=texto) | Q(telefono__icontains=texto) | Q(email__icontains=texto)
        )
    return proveedores


def proveedor_editable(pk):
    """Proveedor activo; uno dado de baja primero se reactiva. Proveedor.DoesNotExist si no."""
    return Proveedor.objects.get(pk=pk, activo=True)


def proveedor_dado_de_baja(pk):
    """Proveedor inactivo, para reactivarlo. Proveedor.DoesNotExist si no lo es."""
    return Proveedor.objects.get(pk=pk, activo=False)


def _guardar(proveedor, datos):
    for campo in CAMPOS_EDITABLES:
        setattr(proveedor, campo, (datos.get(campo) or "").strip())
    proveedor.full_clean()
    proveedor.save()
    return proveedor


def crear_proveedor(usuario, datos):
    _exigir_permiso(usuario)
    return _guardar(Proveedor(), datos)


def modificar_proveedor(usuario, proveedor, datos):
    _exigir_permiso(usuario)
    return _guardar(proveedor, datos)


def dar_de_baja(usuario, proveedor):
    """Baja lógica: sus ingresos y pagos no cambian (RI-11). Un proveedor dado de baja no
    recibe ingresos ni pagos (S-1)."""
    _exigir_permiso(usuario)
    proveedor.activo = False
    proveedor.save(update_fields=["activo", "actualizado_en"])
    return proveedor


def reactivar(usuario, proveedor):
    """Vuelve a activar un proveedor dado de baja (DEC-87, como DEC-85)."""
    _exigir_permiso(usuario)
    proveedor.activo = True
    proveedor.save(update_fields=["activo", "actualizado_en"])
    return proveedor


# CU-05 Registrar ingreso de mercadería, a crédito (DEC-81, DEC-89 a DEC-94).
# El contado, con su pago, llega con CU-07 (etapa 4).

CENTAVO = Decimal("0.01")
MOTIVO_MAXIMO = 255
# Tope de la lista del buscador, como en la venta (DEC-97).
LIMITE_BUSQUEDA = 50


def proveedores_para_ingreso():
    """Solo activos: un proveedor dado de baja no recibe ingresos (S-1)."""
    return Proveedor.objects.filter(activo=True).order_by("nombre", "pk")


def precio_sugerido(producto, proveedor):
    """Último precio de compra del producto con ese proveedor, o None (DEC-90)."""
    return (
        ProductoProveedor.objects.filter(producto=producto, proveedor=proveedor)
        .values_list("precio_compra", flat=True)
        .first()
    )


def precios_sugeridos(usuario, proveedor_id, producto_ids):
    """Último precio de compra de cada producto con ese proveedor (DEC-90), por id."""
    _exigir_permiso(usuario)
    return dict(
        ProductoProveedor.objects.filter(
            proveedor_id=proveedor_id, producto_id__in=producto_ids
        ).values_list("producto_id", "precio_compra")
    )


def buscar_para_ingreso(usuario, texto, proveedor_id=None):
    """Productos activos (también la carne, DEC-94) con su precio sugerido para el proveedor."""
    _exigir_permiso(usuario)
    productos = list(buscar_productos(texto)[: LIMITE_BUSQUEDA + 1])
    precios = dict(
        ProductoProveedor.objects.filter(
            proveedor_id=proveedor_id, producto__in=productos
        ).values_list("producto_id", "precio_compra")
    )
    resultados = [(p, precios.get(p.pk)) for p in productos[:LIMITE_BUSQUEDA]]
    return resultados, len(productos) > LIMITE_BUSQUEDA


def _validar_precio(producto, precio):
    if precio < 0:
        raise ValidationError(f"El precio de {producto} no puede ser negativo.")
    if precio != precio.quantize(CENTAVO):
        raise ValidationError(f"El precio de {producto} admite hasta 2 decimales.")


def registrar_ingreso(usuario, proveedor, lineas, observacion=""):
    """Ingreso a crédito: en una operación, ingreso, detalles, stock y precio de compra.

    `lineas`: [(producto_id, cantidad, precio_unitario)]. La fecha es la de hoy (DEC-93);
    las cantidades siguen DEC-79 sin el tope de la venta (DEC-76); el total es la suma de
    los subtotales redondeados (DEC-89); la carne no mueve stock (DEC-94, RI-07).
    """
    _exigir_permiso(usuario)
    if proveedor is None or not proveedor.activo:
        raise ValidationError("Elegí un proveedor activo.")
    if not lineas:
        raise ValidationError("Agregá al menos un producto.")
    ids = [producto_id for producto_id, _, _ in lineas]
    if len(set(ids)) != len(ids):
        raise ValidationError("Cada producto va en una sola línea.")
    productos = Producto.objects.in_bulk(ids)
    observacion = (observacion or "").strip()
    if len(observacion) > MOTIVO_MAXIMO:
        raise ValidationError(f"La observación admite hasta {MOTIVO_MAXIMO} caracteres.")
    errores = []
    for producto_id, cantidad, precio in lineas:
        producto = productos.get(producto_id)
        if producto is None or not producto.activo:
            errores.append("Uno de los productos no existe o está dado de baja.")
            continue
        for validar, valor in ((validar_cantidad, cantidad), (_validar_precio, precio)):
            try:
                validar(producto, valor)
            except ValidationError as error:
                errores.extend(error.messages)
    if errores:
        raise ValidationError(errores)
    with transaction.atomic():
        ingreso = IngresoMercaderia.objects.create(
            fecha=timezone.localdate(),
            proveedor=proveedor,
            usuario=usuario,
            total=sum(subtotal(c, p) for _, c, p in lineas),
            condicion_pago=CondicionPago.A_CREDITO,
            observacion=observacion,
        )
        for producto_id, cantidad, precio in lineas:
            producto = productos[producto_id]
            DetalleIngreso.objects.create(
                ingreso=ingreso, producto=producto, cantidad=cantidad, precio_unitario=precio
            )
            mover_stock(producto, cantidad)
            # DEC-90: queda como último precio conocido; anular no lo revierte.
            ProductoProveedor.objects.update_or_create(
                producto=producto, proveedor=proveedor, defaults={"precio_compra": precio}
            )
    return ingreso


def _pagos_vigentes(ingreso):
    # Los pagos todavía no se anulan: llega con CU-07 (etapa 4), que filtrará por estado.
    return PagoProveedor.objects.filter(ingreso=ingreso)


def saldo_de_ingreso(ingreso):
    """Total menos pagos vigentes; un ingreso anulado no deja deuda (DEC-21, DEC-81)."""
    if ingreso.estado == EstadoIngreso.ANULADO:
        return Decimal("0.00")
    pagado = _pagos_vigentes(ingreso).aggregate(total=Sum("monto"))["total"] or 0
    return ingreso.total - pagado


def saldo_de_proveedor(proveedor):
    """Suma de los totales de sus ingresos vigentes menos sus pagos (DEC-81); no se guarda."""
    deuda = (
        IngresoMercaderia.objects.filter(
            proveedor=proveedor, estado=EstadoIngreso.VIGENTE
        ).aggregate(total=Sum("total"))["total"]
        or 0
    )
    pagado = (
        PagoProveedor.objects.filter(proveedor=proveedor).aggregate(total=Sum("monto"))["total"]
        or 0
    )
    return Decimal(deuda - pagado).quantize(CENTAVO)


def saldos_de_proveedores(proveedores):
    """Saldo de cada proveedor del listado, con dos consultas en lugar de una por fila."""
    ids = [p.pk for p in proveedores]
    deudas = dict(
        IngresoMercaderia.objects.filter(proveedor_id__in=ids, estado=EstadoIngreso.VIGENTE)
        .values("proveedor_id")
        .annotate(total=Sum("total"))
        .values_list("proveedor_id", "total")
    )
    pagos = dict(
        PagoProveedor.objects.filter(proveedor_id__in=ids)
        .values("proveedor_id")
        .annotate(total=Sum("monto"))
        .values_list("proveedor_id", "total")
    )
    return {i: Decimal(deudas.get(i, 0) - pagos.get(i, 0)).quantize(CENTAVO) for i in ids}


def listar_ingresos(usuario):
    """Más nuevos primero (DEC-95 pagina de a 25 en la vista)."""
    _exigir_permiso(usuario)
    return IngresoMercaderia.objects.select_related("proveedor").order_by("-fecha", "-pk")


def ingreso_con_detalles(usuario, pk):
    _exigir_permiso(usuario)
    return IngresoMercaderia.objects.select_related(
        "proveedor", "usuario", "anulado_por_usuario"
    ).get(pk=pk)


def impedimento_para_anular(ingreso):
    """Por qué no se puede anular, o None: ya anulado o con pagos vigentes (DEC-92)."""
    if ingreso.estado == EstadoIngreso.ANULADO:
        return "El ingreso ya está anulado."
    if _pagos_vigentes(ingreso).exists():
        return "El ingreso tiene pagos: primero hay que anularlos."
    return None


def anular_ingreso(usuario, ingreso, motivo):
    """Anula con motivo y devuelve el stock con mover_stock, aunque quede negativo (DEC-92).

    El ingreso y sus detalles no se tocan; el precio de compra no se revierte (DEC-90).
    """
    _exigir_permiso(usuario)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Escribí por qué se anula el ingreso."})
    if len(motivo) > MOTIVO_MAXIMO:
        raise ValidationError({"motivo": f"El motivo admite hasta {MOTIVO_MAXIMO} caracteres."})
    with transaction.atomic():
        ingreso = IngresoMercaderia.objects.select_for_update().get(pk=ingreso.pk)
        impedimento = impedimento_para_anular(ingreso)
        if impedimento:
            raise ValidationError(impedimento)
        ingreso.estado = EstadoIngreso.ANULADO
        ingreso.anulado_en = timezone.now()
        ingreso.anulado_por_usuario = usuario
        ingreso.motivo_anulacion = motivo
        ingreso.save(
            update_fields=[
                "estado",
                "anulado_en",
                "anulado_por_usuario",
                "motivo_anulacion",
                "actualizado_en",
            ]
        )
        # Como DEC-70: vuelve el stock de los productos que hoy lo controlan.
        for detalle in ingreso.detalleingreso_set.select_related("producto"):
            mover_stock(detalle.producto, -detalle.cantidad)
    return ingreso
