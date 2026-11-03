"""CU-06 integrada en /productos/ (CP-37, DEC-82, DEC-101, DEC-105, R-7, R-8)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalogo.models import Categoria, Producto, UnidadMedida
from apps.catalogo.services import (
    cantidad_con_stock_bajo,
    con_alerta_de_stock,
    listar_productos,
)

pytestmark = pytest.mark.django_db

LISTADO = reverse("catalogo:productos")


def _producto(categoria, nombre, stock, minimo=None, controla=True, activo=True):
    return Producto.objects.create(
        nombre=nombre,
        categoria=categoria,
        precio_venta=Decimal("100"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=controla,
        stock_actual=Decimal(stock),
        stock_minimo=None if minimo is None else Decimal(minimo),
        activo=activo,
    )


@pytest.mark.parametrize(
    ("stock", "minimo", "controla", "activo", "alerta"),
    [
        ("5", "5", True, True, True),  # en el mínimo
        ("4", "5", True, True, True),  # por debajo
        ("6", "5", True, True, False),
        ("0", None, True, True, True),  # sin mínimo, en 0 (DEC-101)
        ("-2", None, True, True, True),  # sin mínimo, negativo
        ("1", None, True, True, False),
        ("0", "0", True, True, True),
        ("-1", "5", False, True, False),  # carne: sin alerta (DEC-36)
        ("0", None, True, False, False),  # dado de baja
    ],
)
def test_cp37_cuando_hay_alerta(categoria, stock, minimo, controla, activo, alerta):
    producto = _producto(categoria, "P", stock, minimo, controla, activo)

    assert con_alerta_de_stock(Producto.objects.all()).get(pk=producto.pk).alerta_stock is alerta
    assert cantidad_con_stock_bajo() == (1 if alerta else 0)


def test_cp37_filtros_de_categoria_y_stock_bajo(admin, categoria):
    otra = Categoria.objects.create(nombre="Bebidas")
    bajo = _producto(categoria, "Bajo", "1", "5")
    normal = _producto(categoria, "Normal", "9", "5")
    bebida = _producto(otra, "Bebida", "0")

    def nombres(**filtros):
        return [p.nombre for p in listar_productos(admin, **filtros)[0]]

    assert nombres() == ["Bajo", "Bebida", "Normal"]
    assert nombres(categoria_id=otra.pk) == ["Bebida"]
    assert nombres(solo_stock_bajo=True) == ["Bajo", "Bebida"]
    assert nombres(categoria_id=categoria.pk, solo_stock_bajo=True) == ["Bajo"]
    assert bajo and bebida and normal


@pytest.mark.parametrize("quien", ["admin", "cajera", "cajera_alta"])
def test_cp37_la_marca_y_los_filtros_se_ven_para_admin_y_cajeras(client, request, categoria, quien):
    _producto(categoria, "Faltante", "0")
    _producto(categoria, "Con stock", "9")
    client.force_login(request.getfixturevalue(quien))

    contenido = client.get(LISTADO).content.decode()
    assert "Solo stock bajo" in contenido and "Todas las categorías" in contenido
    assert contenido.count(">Stock bajo</span>") == 1

    filtrado = client.get(LISTADO, {"stock_bajo": "1"}).content.decode()
    assert "Faltante" in filtrado and "Con stock" not in filtrado


def test_los_duenios_no_acceden_a_la_consulta(client, duenio):
    client.force_login(duenio)

    assert client.get(LISTADO, {"stock_bajo": "1"}).status_code == 403


def test_filtros_invalidos_se_ignoran_y_la_paginacion_los_conserva(client, admin, categoria):
    for i in range(26):
        _producto(categoria, f"Producto {i:02}", "0")
    client.force_login(admin)

    assert client.get(LISTADO, {"categoria": "x", "proveedor": "y"}).status_code == 200
    contenido = client.get(LISTADO, {"stock_bajo": "1"}).content.decode()
    assert "stock_bajo=1&amp;pagina=2" in contenido


def test_sin_resultados_muestra_el_mensaje_del_filtro(client, admin, categoria):
    _producto(categoria, "Con stock", "9")
    client.force_login(admin)

    assert (
        "Sin productos para el filtro" in client.get(LISTADO, {"stock_bajo": "1"}).content.decode()
    )
