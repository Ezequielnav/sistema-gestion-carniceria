from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.caja.models import (
    Caja,
    CierreCajaDetalle,
    ConceptoMovimientoCaja,
    EstadoCaja,
    MedioPago,
    MovimientoCaja,
    TipoMovimientoCaja,
    Turno,
)

pytestmark = pytest.mark.django_db


def _rechaza(crear):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear()


# CP-02 y CP-03 a nivel base (RN-01, RN-02, RI-01)


def test_cp02_segunda_caja_abierta_mismo_turno_y_fecha_se_rechaza(caja, usuario):
    _rechaza(lambda: Caja.objects.create(fecha=caja.fecha, turno=caja.turno, usuario=usuario))


def test_cp02_con_la_caja_anterior_cerrada_se_puede_abrir_otra(caja, usuario):
    caja.estado = EstadoCaja.CERRADA
    caja.cerrada_en = timezone.now()
    caja.save()

    Caja.objects.create(fecha=caja.fecha, turno=caja.turno, usuario=usuario)


def test_cp02_otro_turno_de_la_misma_fecha_se_permite(caja, usuario):
    Caja.objects.create(fecha=caja.fecha, turno=Turno.TARDE, usuario=usuario)


@pytest.mark.parametrize("turno", ["NOCHE", ""])
def test_cp03_turno_distinto_de_manana_y_tarde_se_rechaza(usuario, turno):
    _rechaza(lambda: Caja.objects.create(fecha="2026-01-15", turno=turno, usuario=usuario))


def test_estado_de_caja_fuera_de_la_lista_se_rechaza(usuario):
    _rechaza(
        lambda: Caja.objects.create(
            fecha="2026-01-15", turno=Turno.MANANA, usuario=usuario, estado="PAUSADA"
        )
    )


def test_caja_abierta_con_fecha_de_cierre_se_rechaza(usuario):
    _rechaza(
        lambda: Caja.objects.create(
            fecha="2026-01-15", turno=Turno.MANANA, usuario=usuario, cerrada_en=timezone.now()
        )
    )


def test_medio_de_pago_con_nombre_repetido_se_rechaza(efectivo):
    _rechaza(lambda: MedioPago.objects.create(nombre=efectivo.nombre))


@pytest.mark.parametrize("nombre", ["efectivo", "EFECTIVO", "eFeCtIvO"])
def test_medio_de_pago_repetido_con_otras_mayusculas_se_rechaza(efectivo, nombre):
    _rechaza(lambda: MedioPago.objects.create(nombre=nombre))


def test_cierre_repetido_por_caja_y_medio_de_pago_se_rechaza(caja, efectivo):
    CierreCajaDetalle.objects.create(
        caja=caja, medio_pago=efectivo, monto_sistema=Decimal("10"), monto_contado=Decimal("10")
    )
    _rechaza(
        lambda: CierreCajaDetalle.objects.create(
            caja=caja, medio_pago=efectivo, monto_sistema=Decimal("10"), monto_contado=Decimal("10")
        )
    )


# CP-71 (RI-16)


def test_cp71_monto_inicial_negativo_se_rechaza(usuario):
    _rechaza(
        lambda: Caja.objects.create(
            fecha="2026-01-15", turno=Turno.MANANA, usuario=usuario, monto_inicial=Decimal("-1")
        )
    )


def test_cp71_monto_contado_negativo_se_rechaza(caja, efectivo):
    _rechaza(
        lambda: CierreCajaDetalle.objects.create(
            caja=caja, medio_pago=efectivo, monto_sistema=Decimal("0"), monto_contado=Decimal("-1")
        )
    )


# CP-70 (RI-13): movimiento_caja lleva exactamente la referencia que corresponde al concepto


@pytest.fixture
def movimiento(caja, efectivo, usuario):
    def crear(concepto, **referencias):
        return MovimientoCaja.objects.create(
            caja=caja,
            tipo=TipoMovimientoCaja.INGRESO,
            monto=Decimal("100"),
            medio_pago=efectivo,
            concepto=concepto,
            usuario=usuario,
            **referencias,
        )

    return crear


@pytest.fixture
def referencias(venta, pago_cliente, pago_proveedor):
    return {"venta": venta, "pago_cliente": pago_cliente, "pago_proveedor": pago_proveedor}


VALIDOS = [
    (ConceptoMovimientoCaja.VENTA, ["venta"]),
    (ConceptoMovimientoCaja.PAGO_CLIENTE, ["pago_cliente"]),
    (ConceptoMovimientoCaja.PAGO_PROVEEDOR, ["pago_proveedor"]),
    (ConceptoMovimientoCaja.OTRO, []),
]

INVALIDOS = [
    (ConceptoMovimientoCaja.VENTA, []),
    (ConceptoMovimientoCaja.VENTA, ["venta", "pago_cliente"]),
    (ConceptoMovimientoCaja.VENTA, ["pago_proveedor"]),
    (ConceptoMovimientoCaja.PAGO_CLIENTE, []),
    (ConceptoMovimientoCaja.PAGO_CLIENTE, ["venta"]),
    (ConceptoMovimientoCaja.PAGO_PROVEEDOR, []),
    (ConceptoMovimientoCaja.PAGO_PROVEEDOR, ["pago_proveedor", "pago_cliente"]),
    (ConceptoMovimientoCaja.OTRO, ["venta"]),
    (ConceptoMovimientoCaja.OTRO, ["venta", "pago_cliente", "pago_proveedor"]),
]


@pytest.mark.parametrize(("concepto", "campos"), VALIDOS)
def test_cp70_referencia_coherente_con_el_concepto_se_acepta(
    movimiento, referencias, concepto, campos
):
    movimiento(concepto, **{campo: referencias[campo] for campo in campos})


@pytest.mark.parametrize(("concepto", "campos"), INVALIDOS)
def test_cp70_ninguna_varias_o_distinta_referencia_se_rechaza(
    movimiento, referencias, concepto, campos
):
    _rechaza(lambda: movimiento(concepto, **{campo: referencias[campo] for campo in campos}))


@pytest.mark.parametrize("monto", [Decimal("0"), Decimal("-5")])
def test_cp71_movimiento_de_caja_con_monto_no_positivo_se_rechaza(caja, efectivo, usuario, monto):
    _rechaza(
        lambda: MovimientoCaja.objects.create(
            caja=caja,
            tipo=TipoMovimientoCaja.EGRESO,
            monto=monto,
            medio_pago=efectivo,
            concepto=ConceptoMovimientoCaja.OTRO,
            usuario=usuario,
        )
    )


@pytest.mark.parametrize(("tipo", "concepto"), [("SALIDA", "OTRO"), ("INGRESO", "AJUSTE")])
def test_tipo_o_concepto_de_movimiento_fuera_de_la_lista_se_rechaza(
    caja, efectivo, usuario, tipo, concepto
):
    _rechaza(
        lambda: MovimientoCaja.objects.create(
            caja=caja,
            tipo=tipo,
            monto=Decimal("1"),
            medio_pago=efectivo,
            concepto=concepto,
            usuario=usuario,
        )
    )
