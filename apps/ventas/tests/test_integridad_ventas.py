from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.ventas.models import DetalleVenta, Venta

pytestmark = pytest.mark.django_db


def _rechaza(crear):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear()


def test_cp71_monto_total_negativo_se_rechaza(caja, usuario, efectivo):
    _rechaza(
        lambda: Venta.objects.create(
            caja=caja, usuario=usuario, medio_pago=efectivo, monto_total=Decimal("-1")
        )
    )


@pytest.mark.parametrize(
    "datos",
    [
        {"cantidad": Decimal("0")},
        {"cantidad": Decimal("-0.5")},
        {"precio_unitario": Decimal("-1")},
        {"subtotal": Decimal("-1")},
    ],
)
def test_cp71_detalle_de_venta_con_valores_invalidos_se_rechaza(venta, producto, datos):
    valores = {
        "venta": venta,
        "producto": producto,
        "cantidad": Decimal("1.250"),
        "precio_unitario": Decimal("100.00"),
        "subtotal": Decimal("125.00"),
    }
    valores.update(datos)
    _rechaza(lambda: DetalleVenta.objects.create(**valores))


def test_detalle_de_venta_valido_con_cantidad_por_kg(venta, producto):
    detalle = DetalleVenta.objects.create(
        venta=venta,
        producto=producto,
        cantidad=Decimal("1.250"),
        precio_unitario=Decimal("100.00"),
        subtotal=Decimal("125.00"),
    )

    detalle.refresh_from_db()
    assert detalle.cantidad == Decimal("1.250")
