"""Una sola forma de mostrar cantidades: entera por unidad y con coma y "kg" por kg."""

from decimal import Decimal

import pytest
from django.template import Context, Template

from apps.catalogo.models import UnidadMedida, formatear_cantidad
from apps.ventas.models import DetalleVenta


@pytest.mark.parametrize(
    ("cantidad", "unidad", "esperado"),
    [
        ("2.000", UnidadMedida.UNIDAD, "2"),
        ("1", UnidadMedida.UNIDAD, "1"),
        ("1.250", UnidadMedida.KG, "1,250 kg"),
        ("2", UnidadMedida.KG, "2,000 kg"),
        ("0.075", UnidadMedida.KG, "0,075 kg"),
        ("100.000", UnidadMedida.KG, "100,000 kg"),
    ],
)
def test_formato_de_cantidad_segun_la_unidad(cantidad, unidad, esperado):
    assert formatear_cantidad(Decimal(cantidad), unidad) == esperado


def test_el_filtro_de_plantilla_usa_el_mismo_formato():
    plantilla = Template("{% load cantidades %}{{ c|cantidad:u }}")

    assert plantilla.render(Context({"c": Decimal("1.250"), "u": "KG"})) == "1,250 kg"
    assert plantilla.render(Context({"c": Decimal("2.000"), "u": "UNIDAD"})) == "2"


def test_los_renglones_de_venta_se_leen_con_ese_formato(producto):
    # El de ingreso, en proveedores (R-6: catálogo no importa proveedores).
    assert str(DetalleVenta(producto=producto, cantidad=Decimal("2.000"))) == "Aceite 1 l x 2"
