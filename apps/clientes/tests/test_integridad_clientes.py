from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.clientes.models import (
    Cliente,
    MovimientoCuentaCorriente,
    PagoCliente,
    TipoMovimientoCuentaCorriente,
)

pytestmark = pytest.mark.django_db

Tipo = TipoMovimientoCuentaCorriente


def _rechaza(crear):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear()


def test_cp71_limite_de_credito_negativo_se_rechaza():
    _rechaza(lambda: Cliente.objects.create(nombre="X", limite_credito=Decimal("-1")))


@pytest.mark.parametrize("monto", [Decimal("0"), Decimal("-1")])
def test_cp71_pago_de_cliente_con_monto_no_positivo_se_rechaza(cliente, efectivo, usuario, monto):
    _rechaza(
        lambda: PagoCliente.objects.create(
            cliente=cliente, monto=monto, medio_pago=efectivo, usuario=usuario
        )
    )


@pytest.fixture
def movimiento(cliente):
    def crear(tipo, monto=Decimal("100"), **referencias):
        return MovimientoCuentaCorriente.objects.create(
            cliente=cliente, tipo=tipo, monto=monto, **referencias
        )

    return crear


@pytest.fixture
def referencias(venta, pago_cliente):
    return {"venta": venta, "pago_cliente": pago_cliente}


@pytest.mark.parametrize(
    ("tipo", "campos"),
    [
        (Tipo.VENTA_FIADA, ["venta"]),
        (Tipo.PAGO, ["pago_cliente"]),
        (Tipo.ANTICIPO, ["pago_cliente"]),
    ],
)
def test_referencia_coherente_con_el_tipo_se_acepta(movimiento, referencias, tipo, campos):
    movimiento(tipo, **{campo: referencias[campo] for campo in campos})


@pytest.mark.parametrize(
    ("tipo", "campos"),
    [
        (Tipo.VENTA_FIADA, []),
        (Tipo.VENTA_FIADA, ["pago_cliente"]),
        (Tipo.VENTA_FIADA, ["venta", "pago_cliente"]),
        (Tipo.PAGO, []),
        (Tipo.PAGO, ["venta"]),
        (Tipo.ANTICIPO, ["venta", "pago_cliente"]),
    ],
)
def test_referencia_incoherente_con_el_tipo_se_rechaza(movimiento, referencias, tipo, campos):
    _rechaza(lambda: movimiento(tipo, **{campo: referencias[campo] for campo in campos}))


@pytest.mark.parametrize("monto", [Decimal("0"), Decimal("-1")])
def test_cp71_movimiento_de_cuenta_corriente_con_monto_no_positivo_se_rechaza(
    movimiento, venta, monto
):
    _rechaza(lambda: movimiento(Tipo.VENTA_FIADA, monto=monto, venta=venta))


def test_una_venta_genera_como_mucho_un_movimiento(movimiento, venta):
    movimiento(Tipo.VENTA_FIADA, venta=venta)
    _rechaza(lambda: movimiento(Tipo.VENTA_FIADA, venta=venta))


def test_tipo_de_movimiento_fuera_de_la_lista_se_rechaza(movimiento, venta):
    _rechaza(lambda: movimiento("RECARGO", venta=venta))
