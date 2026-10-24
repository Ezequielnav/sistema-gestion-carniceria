import datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.proveedores.models import (
    CondicionPago,
    DetalleIngreso,
    IngresoMercaderia,
    PagoProveedor,
    ProductoProveedor,
)

pytestmark = pytest.mark.django_db


def _rechaza(crear):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear()


def test_producto_proveedor_repetido_se_rechaza(producto, proveedor):
    ProductoProveedor.objects.create(
        producto=producto, proveedor=proveedor, precio_compra=Decimal("1800")
    )
    _rechaza(
        lambda: ProductoProveedor.objects.create(
            producto=producto, proveedor=proveedor, precio_compra=Decimal("1900")
        )
    )


def test_cp71_precio_de_compra_negativo_se_rechaza(producto, proveedor):
    _rechaza(
        lambda: ProductoProveedor.objects.create(
            producto=producto, proveedor=proveedor, precio_compra=Decimal("-1")
        )
    )


def test_cp71_total_de_ingreso_negativo_se_rechaza(proveedor, usuario):
    _rechaza(
        lambda: IngresoMercaderia.objects.create(
            fecha=datetime.date(2026, 1, 15),
            proveedor=proveedor,
            usuario=usuario,
            total=Decimal("-1"),
            condicion_pago=CondicionPago.CONTADO,
        )
    )


def test_condicion_de_pago_fuera_de_la_lista_se_rechaza(proveedor, usuario):
    _rechaza(
        lambda: IngresoMercaderia.objects.create(
            fecha=datetime.date(2026, 1, 15),
            proveedor=proveedor,
            usuario=usuario,
            total=Decimal("10"),
            condicion_pago="CHEQUE",
        )
    )


@pytest.mark.parametrize(
    "datos",
    [{"cantidad": Decimal("0")}, {"cantidad": Decimal("-1")}, {"precio_unitario": Decimal("-1")}],
)
def test_cp71_detalle_de_ingreso_con_valores_invalidos_se_rechaza(ingreso, producto, datos):
    valores = {
        "ingreso": ingreso,
        "producto": producto,
        "cantidad": Decimal("10"),
        "precio_unitario": Decimal("500"),
    }
    valores.update(datos)
    _rechaza(lambda: DetalleIngreso.objects.create(**valores))


@pytest.mark.parametrize("monto", [Decimal("0"), Decimal("-1")])
def test_cp71_pago_a_proveedor_con_monto_no_positivo_se_rechaza(
    proveedor, efectivo, usuario, monto
):
    _rechaza(
        lambda: PagoProveedor.objects.create(
            proveedor=proveedor, monto=monto, medio_pago=efectivo, usuario=usuario
        )
    )
