"""CU-11: reglas de apps/catalogo/services.py."""

from decimal import Decimal
from unittest import mock

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet

from apps.catalogo.models import Producto, UnidadMedida
from apps.catalogo.services import (
    buscar_productos,
    crear_producto,
    dar_de_baja,
    modificar_producto,
)
from apps.ventas.models import DetalleVenta

pytestmark = pytest.mark.django_db


def _datos(**cambios):
    datos = {
        "nombre": "Yerba 1 kg",
        "categoria": None,
        "plus_interno": "700",
        "precio_venta": Decimal("4200.00"),
        "unidad_medida": UnidadMedida.UNIDAD,
        "controla_stock": True,
        "stock_minimo": Decimal("5"),
    }
    datos.update(cambios)
    return datos


# CP-55 y CP-56 (RN-05; CU-11 A2)


def test_cp55_cajera_sin_permiso_no_crea_productos(cajera):
    with pytest.raises(PermissionDenied):
        crear_producto(cajera, _datos())

    assert not Producto.objects.exists()


def test_cp53_duenio_no_crea_productos(duenio):
    with pytest.raises(PermissionDenied):
        crear_producto(duenio, _datos())


def test_cp56_cajera_con_permiso_crea_un_producto(cajera_alta):
    producto = crear_producto(cajera_alta, _datos())

    assert producto.pk and producto.activo


def test_cajera_con_permiso_no_modifica_ni_da_de_baja(cajera_alta, producto):
    with pytest.raises(PermissionDenied):
        modificar_producto(cajera_alta, producto, _datos())
    with pytest.raises(PermissionDenied):
        dar_de_baja(cajera_alta, producto)

    producto.refresh_from_db()
    assert producto.activo and producto.nombre == "Aceite 1 l"


def test_el_administrador_modifica_un_producto(admin, producto):
    modificar_producto(admin, producto, _datos(nombre="Aceite 900 ml", plus_interno=""))

    producto.refresh_from_db()
    assert producto.nombre == "Aceite 900 ml"
    assert producto.plus_interno is None


# CP-59 para producto (CU-11 A1)


def test_cp59_plus_interno_repetido_no_se_guarda_y_avisa(admin):
    crear_producto(admin, _datos())

    with pytest.raises(ValidationError) as error:
        crear_producto(admin, _datos(nombre="Otro"))

    assert error.value.message_dict == {
        "plus_interno": ["Ya existe un producto con el plus interno 700."]
    }
    assert Producto.objects.count() == 1


def test_cp59_plus_guardado_a_la_vez_por_otra_operacion_avisa_igual(admin):
    crear_producto(admin, _datos())

    # Simula que el otro guardado ocurre entre la verificación previa y el save: la base
    # rechaza el plus y el servicio lo traduce al mismo mensaje.
    with (
        mock.patch.object(QuerySet, "exists", return_value=False),
        pytest.raises(ValidationError) as error,
    ):
        crear_producto(admin, _datos(nombre="Otro"))

    assert error.value.message_dict == {
        "plus_interno": ["Ya existe un producto con el plus interno 700."]
    }
    assert Producto.objects.count() == 1


def test_cp59_al_modificar_tampoco_se_puede_repetir_el_plus(admin):
    crear_producto(admin, _datos())
    otro = crear_producto(admin, _datos(nombre="Otro", plus_interno="701"))

    with pytest.raises(ValidationError):
        modificar_producto(admin, otro, _datos(nombre="Otro", plus_interno="700"))


def test_modificar_conservando_su_propio_plus_se_permite(admin):
    producto = crear_producto(admin, _datos())

    modificar_producto(admin, producto, _datos(precio_venta=Decimal("4500")))


def test_nombre_repetido_no_se_bloquea(admin):
    crear_producto(admin, _datos(plus_interno=None))

    crear_producto(admin, _datos(plus_interno=None))

    assert Producto.objects.filter(nombre="Yerba 1 kg").count() == 2


# RI-16 y RI-07


@pytest.mark.parametrize(
    ("campo", "valor"), [("precio_venta", Decimal("-1")), ("stock_minimo", Decimal("-0.5"))]
)
def test_precio_y_stock_minimo_negativos_se_rechazan(admin, campo, valor):
    with pytest.raises(ValidationError) as error:
        crear_producto(admin, _datos(**{campo: valor}))

    assert error.value.message_dict[campo] == ["No puede ser negativo."]


def test_el_stock_arranca_en_cero_y_no_se_carga_desde_cu11(admin, producto):
    nuevo = crear_producto(admin, _datos(stock_actual=Decimal("50")))
    assert nuevo.stock_actual == 0

    producto.stock_actual = Decimal("7")
    producto.save()
    modificar_producto(admin, producto, _datos(plus_interno=None, stock_actual=Decimal("99")))
    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("7")


# CP-57 (RI-11): baja lógica


def test_cp57_baja_de_un_producto_con_ventas(admin, producto, venta):
    detalle = DetalleVenta.objects.create(
        venta=venta,
        producto=producto,
        cantidad=Decimal("1"),
        precio_unitario=Decimal("2500.00"),
        subtotal=Decimal("2500.00"),
    )

    dar_de_baja(admin, producto)

    producto.refresh_from_db()
    detalle.refresh_from_db()
    assert not producto.activo
    assert detalle.producto_id == producto.pk and detalle.subtotal == Decimal("2500.00")
    assert venta.detalleventa_set.count() == 1


# Búsqueda


def test_busca_por_nombre_o_plus_y_solo_activos_por_defecto(admin):
    yerba = crear_producto(admin, _datos())
    crear_producto(admin, _datos(nombre="Arroz", plus_interno="800"))
    baja = crear_producto(admin, _datos(nombre="Yerba vieja", plus_interno="900"))
    dar_de_baja(admin, baja)

    assert list(buscar_productos("yerb")) == [yerba]
    assert list(buscar_productos("700")) == [yerba]
    assert list(buscar_productos("yerb", incluir_inactivos=True)) == [yerba, baja]
    assert len(buscar_productos()) == 2
