"""Servicio único de stock y de cantidades en catálogo (DEC-96, R-1 y R-2)."""

from decimal import Decimal
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError

from apps.catalogo.models import Producto, UnidadMedida
from apps.catalogo.services import STOCK_MAXIMO, mover_stock, validar_cantidad

pytestmark = pytest.mark.django_db

APPS = Path(__file__).resolve().parents[2]


@pytest.fixture
def queso(categoria):
    return Producto.objects.create(
        nombre="Queso",
        categoria=categoria,
        precio_venta=Decimal("8000.00"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=True,
    )


# validar_cantidad (RI-16, DEC-48, DEC-79)


@pytest.mark.parametrize("cantidad", ["0", "-1"])
def test_la_cantidad_tiene_que_ser_mayor_a_0(producto, cantidad):
    with pytest.raises(ValidationError, match="tiene que ser mayor a 0"):
        validar_cantidad(producto, Decimal(cantidad))


def test_por_unidad_la_cantidad_es_entera(producto):
    validar_cantidad(producto, Decimal("3"))

    with pytest.raises(ValidationError, match="la cantidad tiene que ser entera"):
        validar_cantidad(producto, Decimal("1.5"))


def test_por_kg_hasta_3_decimales(queso):
    validar_cantidad(queso, Decimal("0.750"))

    with pytest.raises(ValidationError, match="hasta 3 decimales"):
        validar_cantidad(queso, Decimal("0.7501"))


def test_sin_el_tope_de_la_venta(queso, producto):
    # DEC-76 es solo de la venta: el catálogo acepta más de 100.
    validar_cantidad(queso, Decimal("150"))
    validar_cantidad(producto, Decimal("120"))


# mover_stock (RI-07, DEC-46)


def test_suma_y_resta_stock_si_el_producto_lo_controla(producto):
    mover_stock(producto, Decimal("5"))
    mover_stock(producto, Decimal("-2"))

    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("3")


def test_puede_quedar_negativo(producto):
    mover_stock(producto, Decimal("-4"))

    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("-4")


def test_sin_control_de_stock_no_cambia(producto):
    producto.controla_stock = False
    producto.save()

    mover_stock(producto, Decimal("5"))

    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("0")


def test_solo_catalogo_cambia_el_stock_actual():
    # R-1: ningún otro módulo actualiza stock_actual por su cuenta.
    otros = [
        ruta
        for ruta in APPS.rglob("*.py")
        if "tests" not in ruta.parts
        and "migrations" not in ruta.parts
        and ruta != APPS / "catalogo" / "services.py"
        and 'F("stock_actual")' in ruta.read_text(encoding="utf-8")
    ]

    assert otros == []


# CP-143: rango de stock_actual (L19, DEC-169, DEC-175)


def test_cp143_hasta_el_maximo_de_la_columna_se_mueve(producto):
    mover_stock(producto, STOCK_MAXIMO)

    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("999999999.999")


def test_cp143_pasar_el_maximo_se_rechaza_con_mensaje_y_no_cambia(producto):
    mover_stock(producto, STOCK_MAXIMO)

    with pytest.raises(ValidationError) as error:
        mover_stock(producto, Decimal("0.001"))

    assert error.value.messages == [
        f"El stock de «{producto.nombre}» quedaría fuera del rango permitido."
    ]
    producto.refresh_from_db()
    assert producto.stock_actual == STOCK_MAXIMO


def test_cp143_el_negativo_sigue_permitido_hasta_el_minimo(producto):
    # DEC-46 se mantiene dentro del rango; por debajo del mínimo, mensaje.
    mover_stock(producto, -STOCK_MAXIMO)

    with pytest.raises(ValidationError):
        mover_stock(producto, Decimal("-0.001"))

    producto.refresh_from_db()
    assert producto.stock_actual == -STOCK_MAXIMO
