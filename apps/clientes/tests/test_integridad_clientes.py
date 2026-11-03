"""Restricciones de la base de clientes y cuentas corrientes (05, sección 7.4; H4, etapa 1)."""

import datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clientes.models import (
    Cliente,
    EstadoPagoCliente,
    MovimientoCuentaCorriente,
    PagoCliente,
    TipoMovimientoCuentaCorriente,
)

pytestmark = pytest.mark.django_db

Tipo = TipoMovimientoCuentaCorriente
FECHA_ORIGEN = datetime.date(2026, 1, 2)


def _rechaza(crear):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear()


def test_cp71_limite_de_credito_negativo_se_rechaza():
    _rechaza(lambda: Cliente.objects.create(nombre="X", limite_credito=Decimal("-1")))


def test_dec117_cliente_con_direccion_y_observaciones():
    cliente = Cliente.objects.create(
        nombre="X", direccion="San Martín 1", observaciones="Paga a fin de mes"
    )

    assert Cliente.objects.get(pk=cliente.pk).observaciones == "Paga a fin de mes"


@pytest.mark.parametrize("monto", [Decimal("0"), Decimal("-1")])
def test_cp71_pago_de_cliente_con_monto_no_positivo_se_rechaza(cliente, efectivo, usuario, monto):
    _rechaza(
        lambda: PagoCliente.objects.create(
            cliente=cliente, monto=monto, medio_pago=efectivo, usuario=usuario
        )
    )


# DEC-113: los datos de la anulación de un cobro están si y solo si está anulado.


def test_cobro_nuevo_queda_vigente_y_sin_caja(pago_cliente):
    assert pago_cliente.estado == EstadoPagoCliente.VIGENTE
    assert pago_cliente.entra_a_caja is False


def test_cobro_anulado_con_todos_sus_datos_se_acepta(pago_cliente, usuario):
    pago_cliente.estado = EstadoPagoCliente.ANULADO
    pago_cliente.anulado_en = timezone.now()
    pago_cliente.anulado_por_usuario = usuario
    pago_cliente.motivo_anulacion = "Error de carga"
    pago_cliente.save()


@pytest.mark.parametrize(
    "cambios",
    [
        {"estado": EstadoPagoCliente.ANULADO},
        {"estado": EstadoPagoCliente.ANULADO, "motivo_anulacion": "Error"},
        {"motivo_anulacion": "Error"},
        {"estado": "BORRADO"},
    ],
)
def test_cobro_con_datos_de_anulacion_incoherentes_se_rechaza(pago_cliente, cambios):
    for campo, valor in cambios.items():
        setattr(pago_cliente, campo, valor)

    _rechaza(pago_cliente.save)


@pytest.fixture
def movimiento(cliente):
    def crear(tipo, monto=Decimal("100"), **campos):
        return MovimientoCuentaCorriente.objects.create(
            cliente=cliente, tipo=tipo, monto=monto, **campos
        )

    return crear


@pytest.fixture
def saldo_inicial(movimiento):
    return movimiento(Tipo.SALDO_INICIAL, fecha_origen=FECHA_ORIGEN, motivo="Deuda anterior")


@pytest.fixture
def referencias(venta, pago_cliente, saldo_inicial):
    return {"venta": venta, "pago_cliente": pago_cliente, "saldo_inicial": saldo_inicial}


def _campos(tipo, nombres, referencias):
    campos = {nombre: referencias[nombre] for nombre in nombres}
    if tipo == Tipo.SALDO_INICIAL:
        campos.update(fecha_origen=FECHA_ORIGEN, motivo="Deuda anterior")
    elif tipo == Tipo.ANULACION_SALDO_INICIAL:
        campos["motivo"] = "Error de carga"
    return campos


@pytest.mark.parametrize(
    ("tipo", "nombres"),
    [
        (Tipo.VENTA_FIADA, ["venta"]),
        (Tipo.ANULACION_VENTA, ["venta"]),
        (Tipo.PAGO, ["pago_cliente"]),
        (Tipo.ANULACION_PAGO, ["pago_cliente"]),
        (Tipo.SALDO_INICIAL, []),
        (Tipo.ANULACION_SALDO_INICIAL, ["saldo_inicial"]),
    ],
)
def test_referencia_coherente_con_el_tipo_se_acepta(movimiento, referencias, tipo, nombres):
    movimiento(tipo, **_campos(tipo, nombres, referencias))


@pytest.mark.parametrize(
    ("tipo", "nombres"),
    [
        (Tipo.VENTA_FIADA, []),
        (Tipo.VENTA_FIADA, ["pago_cliente"]),
        (Tipo.VENTA_FIADA, ["venta", "pago_cliente"]),
        (Tipo.ANULACION_VENTA, ["saldo_inicial"]),
        (Tipo.PAGO, []),
        (Tipo.PAGO, ["venta"]),
        (Tipo.ANULACION_PAGO, ["pago_cliente", "saldo_inicial"]),
        (Tipo.SALDO_INICIAL, ["venta"]),
        (Tipo.SALDO_INICIAL, ["saldo_inicial"]),
        (Tipo.ANULACION_SALDO_INICIAL, []),
        (Tipo.ANULACION_SALDO_INICIAL, ["pago_cliente"]),
    ],
)
def test_referencia_incoherente_con_el_tipo_se_rechaza(movimiento, referencias, tipo, nombres):
    _rechaza(lambda: movimiento(tipo, **_campos(tipo, nombres, referencias)))


def test_anticipo_ya_no_es_un_tipo_valido(movimiento, pago_cliente):
    # DEC-111: no hay saldo a favor.
    _rechaza(lambda: movimiento("ANTICIPO", pago_cliente=pago_cliente))


# DEC-119: solo el saldo inicial tiene fecha de origen, y él y su anulación llevan motivo.


@pytest.mark.parametrize(
    "campos",
    [{"motivo": "Deuda anterior"}, {"fecha_origen": FECHA_ORIGEN}],
    ids=["sin-fecha-de-origen", "sin-motivo"],
)
def test_saldo_inicial_sin_fecha_de_origen_o_motivo_se_rechaza(movimiento, campos):
    _rechaza(lambda: movimiento(Tipo.SALDO_INICIAL, **campos))


def test_anulacion_de_saldo_inicial_sin_motivo_se_rechaza(movimiento, saldo_inicial):
    _rechaza(lambda: movimiento(Tipo.ANULACION_SALDO_INICIAL, saldo_inicial=saldo_inicial))


@pytest.mark.parametrize(
    "campos", [{"fecha_origen": FECHA_ORIGEN}, {"motivo": "Algo"}], ids=["fecha", "motivo"]
)
def test_venta_fiada_con_datos_de_saldo_inicial_se_rechaza(movimiento, venta, campos):
    _rechaza(lambda: movimiento(Tipo.VENTA_FIADA, venta=venta, **campos))


@pytest.mark.parametrize("monto", [Decimal("0"), Decimal("-1")])
def test_cp71_movimiento_de_cuenta_corriente_con_monto_no_positivo_se_rechaza(
    movimiento, venta, monto
):
    _rechaza(lambda: movimiento(Tipo.VENTA_FIADA, monto=monto, venta=venta))


# DEC-113 y RI-18: una venta tiene su cargo y a lo sumo una anulación; un cobro, su abono y a lo
# sumo una anulación; un saldo inicial, a lo sumo una anulación.


def test_una_venta_tiene_un_cargo_y_una_anulacion(movimiento, venta):
    movimiento(Tipo.VENTA_FIADA, venta=venta)
    movimiento(Tipo.ANULACION_VENTA, venta=venta)

    _rechaza(lambda: movimiento(Tipo.VENTA_FIADA, venta=venta))
    _rechaza(lambda: movimiento(Tipo.ANULACION_VENTA, venta=venta))


def test_un_cobro_tiene_un_abono_y_una_anulacion(movimiento, pago_cliente):
    movimiento(Tipo.PAGO, pago_cliente=pago_cliente)
    movimiento(Tipo.ANULACION_PAGO, pago_cliente=pago_cliente)

    _rechaza(lambda: movimiento(Tipo.PAGO, pago_cliente=pago_cliente))
    _rechaza(lambda: movimiento(Tipo.ANULACION_PAGO, pago_cliente=pago_cliente))


def test_ri18_un_saldo_inicial_tiene_a_lo_sumo_una_anulacion(movimiento, saldo_inicial):
    movimiento(Tipo.ANULACION_SALDO_INICIAL, saldo_inicial=saldo_inicial, motivo="Error")

    _rechaza(
        lambda: movimiento(Tipo.ANULACION_SALDO_INICIAL, saldo_inicial=saldo_inicial, motivo="Otro")
    )


def test_tipo_de_movimiento_fuera_de_la_lista_se_rechaza(movimiento, venta):
    _rechaza(lambda: movimiento("RECARGO", venta=venta))
