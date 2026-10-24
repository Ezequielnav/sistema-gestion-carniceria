from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError

from apps.catalogo.models import Categoria, Producto, UnidadMedida

pytestmark = pytest.mark.django_db


def _rechaza(crear):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear()


def _producto(**datos):
    valores = {
        "nombre": "Yerba 1 kg",
        "precio_venta": Decimal("3000.00"),
        "unidad_medida": UnidadMedida.UNIDAD,
        "controla_stock": True,
    }
    valores.update(datos)
    return Producto.objects.create(**valores)


def test_plus_interno_repetido_se_rechaza():
    _producto(plus_interno="1001")
    _rechaza(lambda: _producto(nombre="Otro", plus_interno="1001"))


def test_varios_productos_sin_plus_interno_se_permiten():
    _producto(plus_interno=None)
    _producto(nombre="Otro", plus_interno=None)


def test_plus_interno_vacio_se_rechaza():
    _rechaza(lambda: _producto(plus_interno=""))


def test_categoria_con_nombre_repetido_se_rechaza(categoria):
    _rechaza(lambda: Categoria.objects.create(nombre=categoria.nombre))


def test_categoria_repetida_con_otras_mayusculas_se_rechaza(categoria):
    _rechaza(lambda: Categoria.objects.create(nombre=categoria.nombre.upper()))


def test_unidad_de_medida_fuera_de_la_lista_se_rechaza():
    _rechaza(lambda: _producto(unidad_medida="LITRO"))


def test_cp71_precio_de_venta_negativo_se_rechaza():
    _rechaza(lambda: _producto(precio_venta=Decimal("-0.01")))


def test_cp71_stock_minimo_negativo_se_rechaza():
    _rechaza(lambda: _producto(stock_minimo=Decimal("-1")))


def test_stock_actual_arranca_en_cero():
    assert _producto().stock_actual == 0


# CP-58 (RI-11): no se puede borrar un registro referenciado


def test_cp58_el_orm_impide_borrar_una_categoria_con_productos(producto):
    with pytest.raises(ProtectedError):
        producto.categoria.delete()


def _borrar_por_sql(categoria):
    # Las claves foráneas de Django son diferidas: se fuerza el control inmediato para que el
    # rechazo ocurra en esta sentencia y no quede postergado al final de la transacción.
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("DELETE FROM categoria WHERE id = %s", [categoria.pk])


def test_cp58_la_base_impide_borrar_una_categoria_con_productos(producto):
    _rechaza(lambda: _borrar_por_sql(producto.categoria))

    assert Categoria.objects.filter(pk=producto.categoria.pk).exists()


def test_cp58_la_base_si_permite_borrar_una_categoria_sin_productos(categoria):
    # Control: el mismo borrado sin referencias funciona, así la prueba anterior no pasa en falso.
    _borrar_por_sql(categoria)

    assert not Categoria.objects.filter(pk=categoria.pk).exists()
