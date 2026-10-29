"""CU-05 ingreso de mercadería a crédito y su anulación (H3, etapa 3).

CP-30, CP-31, CP-32, CP-93, CP-100 y CP-101; DEC-79, DEC-81, DEC-89 a DEC-94.
"""

import json
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.catalogo.models import Producto, UnidadMedida
from apps.proveedores.models import (
    CondicionPago,
    EstadoIngreso,
    IngresoMercaderia,
    PagoProveedor,
    ProductoProveedor,
)
from apps.proveedores.services import (
    anular_ingreso,
    buscar_para_ingreso,
    registrar_ingreso,
    saldo_de_ingreso,
    saldo_de_proveedor,
)

pytestmark = pytest.mark.django_db

NUEVO = reverse("proveedores:ingreso_nuevo")
BUSCAR = reverse("proveedores:ingreso_buscar")
CONFIRMAR = reverse("proveedores:ingreso_confirmar")
PRODUCTO = reverse("proveedores:ingreso_producto")


@pytest.fixture
def aceite(producto):
    producto.stock_actual = Decimal("3")
    producto.save()
    return producto


@pytest.fixture
def bondiola(categoria):
    return Producto.objects.create(
        nombre="Bondiola",
        categoria=categoria,
        precio_venta=Decimal("8900"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=True,
    )


@pytest.fixture
def asado(categoria):
    # Carne: sin control de stock (DEC-36, DEC-94).
    return Producto.objects.create(
        nombre="Asado",
        categoria=categoria,
        precio_venta=Decimal("9800"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=False,
    )


def _linea(producto, cantidad, precio):
    return (producto.pk, Decimal(cantidad), Decimal(precio))


# CP-30, CP-31, CP-32 y DEC-89, DEC-93


def test_cp30_cp31_cp32_ingreso_a_credito(admin, proveedor, aceite, bondiola):
    ingreso = registrar_ingreso(
        admin,
        proveedor,
        [_linea(aceite, "2", "1000"), _linea(bondiola, "1.333", "3333.33")],
        "  Remito 0001-123  ",
    )

    assert ingreso.condicion_pago == CondicionPago.A_CREDITO
    assert ingreso.fecha == timezone.localdate() and ingreso.observacion == "Remito 0001-123"
    # DEC-89: 2000 + redondeo de 1,333 × 3333,33 = 4443,33
    assert ingreso.total == Decimal("6443.33")
    aceite.refresh_from_db()
    bondiola.refresh_from_db()
    assert aceite.stock_actual == Decimal("5") and bondiola.stock_actual == Decimal("1.333")
    precios = {d.producto_id: d.precio_unitario for d in ingreso.detalleingreso_set.all()}
    assert precios == {aceite.pk: Decimal("1000"), bondiola.pk: Decimal("3333.33")}
    assert saldo_de_ingreso(ingreso) == Decimal("6443.33")
    assert saldo_de_proveedor(proveedor) == Decimal("6443.33")


def test_cp32_el_saldo_descuenta_pagos(admin, usuario, proveedor, aceite, efectivo):
    ingreso = registrar_ingreso(admin, proveedor, [_linea(aceite, "2", "1000")])
    PagoProveedor.objects.create(
        proveedor=proveedor,
        ingreso=ingreso,
        monto=Decimal("500"),
        medio_pago=efectivo,
        usuario=usuario,
    )

    assert saldo_de_ingreso(ingreso) == Decimal("1500")
    assert saldo_de_proveedor(proveedor) == Decimal("1500.00")


def test_dec94_la_carne_suma_a_la_deuda_sin_mover_stock(admin, proveedor, asado):
    ingreso = registrar_ingreso(admin, proveedor, [_linea(asado, "20.500", "6000")])

    asado.refresh_from_db()
    assert asado.stock_actual == 0
    assert ingreso.total == Decimal("123000.00") == saldo_de_proveedor(proveedor)


# CP-93 (DEC-79, sin el tope de DEC-76)


def test_cp93_cantidades_del_ingreso(admin, proveedor, aceite, bondiola):
    with pytest.raises(ValidationError):
        registrar_ingreso(admin, proveedor, [_linea(aceite, "1.5", "1000")])
    with pytest.raises(ValidationError):
        registrar_ingreso(admin, proveedor, [_linea(bondiola, "0.0005", "1000")])
    with pytest.raises(ValidationError):
        registrar_ingreso(admin, proveedor, [_linea(aceite, "0", "1000")])

    ingreso = registrar_ingreso(
        admin, proveedor, [_linea(aceite, "150", "1000"), _linea(bondiola, "150.125", "10")]
    )
    assert ingreso.detalleingreso_set.count() == 2


@pytest.mark.parametrize(
    ("lineas_de", "mensaje"),
    [
        (lambda a: [], "Agregá al menos un producto."),
        (lambda a: [_linea(a, "1", "-1")], "El precio de Aceite 1 l no puede ser negativo."),
        (lambda a: [_linea(a, "1", "1.005")], "El precio de Aceite 1 l admite hasta 2 decimales."),
        (
            lambda a: [_linea(a, "1", "10"), _linea(a, "2", "10")],
            "Cada producto va en una sola línea.",
        ),
    ],
)
def test_lineas_invalidas_no_guardan_nada(admin, proveedor, aceite, lineas_de, mensaje):
    with pytest.raises(ValidationError) as error:
        registrar_ingreso(admin, proveedor, lineas_de(aceite))

    assert mensaje in error.value.messages
    assert not IngresoMercaderia.objects.exists()
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("3")


def test_productos_y_proveedores_dados_de_baja_se_rechazan(admin, proveedor, aceite):
    aceite.activo = False
    aceite.save()
    with pytest.raises(ValidationError):
        registrar_ingreso(admin, proveedor, [_linea(aceite, "1", "10")])

    aceite.activo, proveedor.activo = True, False
    aceite.save()
    proveedor.save()
    with pytest.raises(ValidationError):
        registrar_ingreso(admin, proveedor, [_linea(aceite, "1", "10")])
    assert not IngresoMercaderia.objects.exists()


# CP-100 (DEC-90)


def test_cp100_precio_de_compra_sugerido_y_actualizado(admin, proveedor, aceite):
    assert buscar_para_ingreso(admin, "aceite", proveedor.pk)[0] == [(aceite, None)]

    ingreso = registrar_ingreso(admin, proveedor, [_linea(aceite, "1", "1800")])
    assert buscar_para_ingreso(admin, "aceite", proveedor.pk)[0] == [(aceite, Decimal("1800"))]

    registrar_ingreso(admin, proveedor, [_linea(aceite, "1", "1950")])
    assert ProductoProveedor.objects.get().precio_compra == Decimal("1950")

    anular_ingreso(admin, ingreso, "Remito duplicado")
    assert ProductoProveedor.objects.get().precio_compra == Decimal("1950")


# CP-101 (DEC-92)


def test_cp101_anular_devuelve_el_stock_aunque_quede_negativo(admin, proveedor, aceite, asado):
    ingreso = registrar_ingreso(
        admin, proveedor, [_linea(aceite, "5", "1000"), _linea(asado, "2", "10")]
    )
    Producto.objects.filter(pk=aceite.pk).update(stock_actual=Decimal("1"))  # se vendieron 7

    anular_ingreso(admin, ingreso, "  Mercadería devuelta  ")

    ingreso.refresh_from_db()
    assert ingreso.estado == EstadoIngreso.ANULADO
    assert (ingreso.anulado_por_usuario, ingreso.motivo_anulacion) == (admin, "Mercadería devuelta")
    assert ingreso.anulado_en is not None
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("-4")
    assert saldo_de_ingreso(ingreso) == 0 and saldo_de_proveedor(proveedor) == 0
    assert ingreso.detalleingreso_set.count() == 2


def test_cp101_sin_motivo_ya_anulado_o_con_pagos_se_rechaza(
    admin, usuario, proveedor, aceite, efectivo
):
    ingreso = registrar_ingreso(admin, proveedor, [_linea(aceite, "2", "1000")])
    with pytest.raises(ValidationError):
        anular_ingreso(admin, ingreso, "   ")

    PagoProveedor.objects.create(
        proveedor=proveedor,
        ingreso=ingreso,
        monto=Decimal("100"),
        medio_pago=efectivo,
        usuario=usuario,
    )
    with pytest.raises(ValidationError) as error:
        anular_ingreso(admin, ingreso, "Error")
    assert "primero hay que anularlos" in error.value.messages[0]

    PagoProveedor.objects.all().delete()
    anular_ingreso(admin, ingreso, "Error")
    with pytest.raises(ValidationError):
        anular_ingreso(admin, ingreso, "Otra vez")
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("3")


@pytest.mark.parametrize("quien", ["cajera_alta", "cajera", "duenio"])
def test_el_ingreso_es_solo_del_administrador(request, admin, proveedor, aceite, quien):
    usuario = request.getfixturevalue(quien)
    ingreso = registrar_ingreso(admin, proveedor, [_linea(aceite, "1", "10")])

    with pytest.raises(PermissionDenied):
        registrar_ingreso(usuario, proveedor, [_linea(aceite, "1", "10")])
    with pytest.raises(PermissionDenied):
        anular_ingreso(usuario, ingreso, "No")
    assert IngresoMercaderia.objects.count() == 1


# Pantallas


def test_el_administrador_registra_un_ingreso_desde_la_pantalla(client, admin, proveedor, aceite):
    client.force_login(admin)
    assert client.get(NUEVO).status_code == 200

    datos = client.get(BUSCAR, {"q": "acei", "proveedor": proveedor.pk}).json()
    assert datos["resultados"][0]["id"] == aceite.pk and datos["resultados"][0]["precio"] == ""

    respuesta = client.post(
        CONFIRMAR,
        {
            "proveedor": proveedor.pk,
            "observacion": "Remito 12",
            "lineas": json.dumps([{"producto": aceite.pk, "cantidad": "4", "precio": "1800"}]),
        },
    )

    ingreso = IngresoMercaderia.objects.get()
    assert respuesta.json() == {"detalle": reverse("proveedores:ingreso", args=[ingreso.pk])}
    detalle = client.get(respuesta.json()["detalle"]).content.decode()
    assert "Remito 12" in detalle and "$ 7.200,00" in detalle and "Anular ingreso" in detalle
    assert client.get(BUSCAR, {"ids": aceite.pk, "proveedor": proveedor.pk}).json() == {
        "precios": {str(aceite.pk): "1800.00"}
    }
    listado = client.get(reverse("proveedores:ingresos")).content.decode()
    assert "Remito 12" in listado
    assert "$ 7.200,00" in client.get(reverse("proveedores:proveedores")).content.decode()


def test_los_errores_del_ingreso_vuelven_como_mensajes(client, admin, proveedor, aceite):
    client.force_login(admin)

    sin_proveedor = client.post(CONFIRMAR, {"lineas": "[]"})
    sin_lineas = client.post(CONFIRMAR, {"proveedor": proveedor.pk, "lineas": "[]"})
    mal_formadas = client.post(CONFIRMAR, {"proveedor": proveedor.pk, "lineas": "no-es-json"})

    assert "Elegí un proveedor." in sin_proveedor.json()["errores"]
    assert sin_lineas.json() == {"errores": ["Agregá al menos un producto."]}
    assert mal_formadas.json() == {"errores": ["La lista de productos no es válida."]}
    assert not IngresoMercaderia.objects.exists()


def test_alta_de_producto_desde_el_ingreso(client, admin, categoria):
    client.force_login(admin)
    datos = {
        "producto-nombre": "Yerba 1 kg",
        "producto-categoria": categoria.pk,
        "producto-precio_venta": "4200",
        "producto-unidad_medida": "UNIDAD",
        "producto-controla_stock": "on",
    }

    producto = client.post(PRODUCTO, datos).json()["producto"]

    assert producto["nombre"] == "Yerba 1 kg" and producto["precio"] == ""
    assert Producto.objects.get(pk=producto["id"]).stock_actual == 0
    errores = client.post(PRODUCTO, {"producto-nombre": ""}).json()["errores"]
    assert "producto-nombre" in errores or "nombre" in errores


def test_anular_desde_el_detalle(client, admin, proveedor, aceite):
    client.force_login(admin)
    ingreso = registrar_ingreso(admin, proveedor, [_linea(aceite, "2", "1000")])
    url = reverse("proveedores:ingreso_anular", args=[ingreso.pk])

    sin_motivo = client.post(url, {"motivo": ""})
    assert sin_motivo.status_code == 400
    respuesta = client.post(url, {"motivo": "Cargado dos veces"})

    assert respuesta.url == reverse("proveedores:ingreso", args=[ingreso.pk])
    ingreso.refresh_from_db()
    assert ingreso.estado == EstadoIngreso.ANULADO
    detalle = client.get(respuesta.url).content.decode()
    assert "Anulado" in detalle and "Cargado dos veces" in detalle
    assert "Anular ingreso</button>" not in detalle


@pytest.mark.parametrize("quien", ["cajera_alta", "cajera", "duenio"])
def test_las_pantallas_del_ingreso_dan_403_a_quien_no_es_administrador(
    client, request, admin, proveedor, aceite, quien
):
    ingreso = registrar_ingreso(admin, proveedor, [_linea(aceite, "1", "10")])
    client.force_login(request.getfixturevalue(quien))

    for url in (
        reverse("proveedores:ingresos"),
        NUEVO,
        BUSCAR,
        reverse("proveedores:ingreso", args=[ingreso.pk]),
    ):
        assert client.get(url).status_code == 403, url
    for url in (CONFIRMAR, PRODUCTO, reverse("proveedores:ingreso_anular", args=[ingreso.pk])):
        assert client.post(url, {}).status_code == 403, url
