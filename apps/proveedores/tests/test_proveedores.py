"""CU-13 Gestionar proveedores (CP-99, DEC-87, DEC-88)."""

from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.catalogo.models import Producto, UnidadMedida
from apps.catalogo.services import proveedores_para_filtrar
from apps.proveedores.models import ProductoProveedor, Proveedor
from apps.proveedores.services import (
    crear_proveedor,
    dar_de_baja,
    listar_proveedores,
    modificar_proveedor,
    reactivar,
)

pytestmark = pytest.mark.django_db

LISTADO = reverse("proveedores:proveedores")
NUEVO = reverse("proveedores:nuevo")


def _editar(proveedor):
    return reverse("proveedores:editar", args=[proveedor.pk])


def _baja(proveedor):
    return reverse("proveedores:baja", args=[proveedor.pk])


def _reactivar(proveedor):
    return reverse("proveedores:reactivar", args=[proveedor.pk])


# Servicio


def test_cp99_alta_modificacion_baja_y_reactivacion(admin):
    proveedor = crear_proveedor(
        admin, {"nombre": "  Frigorífico Sur ", "telefono": "", "email": ""}
    )
    assert proveedor.nombre == "Frigorífico Sur" and proveedor.activo

    modificar_proveedor(admin, proveedor, {"nombre": "Frigorífico Sur", "telefono": "4444-5555"})
    proveedor.refresh_from_db()
    assert proveedor.telefono == "4444-5555" and proveedor.email == ""

    dar_de_baja(admin, proveedor)
    assert list(listar_proveedores(admin)) == []
    assert list(listar_proveedores(admin, incluir_inactivos=True)) == [proveedor]

    reactivar(admin, proveedor)
    assert list(listar_proveedores(admin)) == [proveedor]


def test_cp99_el_nombre_es_obligatorio_y_el_email_se_valida(admin):
    with pytest.raises(ValidationError) as error:
        crear_proveedor(admin, {"nombre": "   ", "email": "no-es-un-email"})
    assert {"nombre", "email"} <= set(error.value.message_dict)
    assert not Proveedor.objects.exists()


def test_dec87_el_nombre_repetido_no_se_bloquea(admin, proveedor):
    crear_proveedor(admin, {"nombre": proveedor.nombre})

    assert Proveedor.objects.filter(nombre=proveedor.nombre).count() == 2


def test_la_busqueda_va_por_nombre_telefono_o_email(admin, proveedor):
    otro = crear_proveedor(admin, {"nombre": "Distribuidora Norte", "email": "ventas@norte.test"})

    assert list(listar_proveedores(admin, "norte")) == [otro]
    assert list(listar_proveedores(admin, "prueba")) == [proveedor]


@pytest.mark.parametrize("quien", ["cajera_alta", "cajera", "duenio"])
def test_dec88_el_servicio_es_solo_del_administrador(request, proveedor, quien):
    usuario = request.getfixturevalue(quien)

    for operacion in (
        lambda: listar_proveedores(usuario),
        lambda: crear_proveedor(usuario, {"nombre": "X"}),
        lambda: modificar_proveedor(usuario, proveedor, {"nombre": "X"}),
        lambda: dar_de_baja(usuario, proveedor),
        lambda: reactivar(usuario, proveedor),
    ):
        with pytest.raises(PermissionDenied):
            operacion()
    proveedor.refresh_from_db()
    assert proveedor.nombre == "Proveedor de prueba" and proveedor.activo


# Pantallas


def test_cp99_el_administrador_gestiona_desde_la_pantalla(client, admin):
    client.force_login(admin)

    assert client.post(NUEVO, {"nombre": "Frigorífico Sur", "telefono": "4444"}).url == LISTADO
    proveedor = Proveedor.objects.get()
    assert "Frigorífico Sur" in client.get(LISTADO).content.decode()

    client.post(_editar(proveedor), {"nombre": "Frigorífico del Sur", "email": "a@b.test"})
    proveedor.refresh_from_db()
    assert (proveedor.nombre, proveedor.email) == ("Frigorífico del Sur", "a@b.test")

    assert "¿Dar de baja" in client.get(_baja(proveedor)).content.decode()
    client.post(_baja(proveedor))
    proveedor.refresh_from_db()
    assert not proveedor.activo
    assert _editar(proveedor) not in client.get(LISTADO).content.decode()

    inactivos = client.get(LISTADO, {"inactivos": "1"}).content.decode()
    assert "Dado de baja" in inactivos and _reactivar(proveedor) in inactivos
    client.post(_reactivar(proveedor))
    proveedor.refresh_from_db()
    assert proveedor.activo


def test_el_error_del_nombre_se_ve_junto_al_campo(client, admin):
    client.force_login(admin)

    respuesta = client.post(NUEVO, {"nombre": ""})

    assert "nombre" in respuesta.context["form"].errors
    assert not Proveedor.objects.exists()


def test_un_dado_de_baja_no_se_edita_y_reactivar_es_solo_por_post(client, admin, proveedor):
    client.force_login(admin)
    assert client.get(_reactivar(proveedor)).status_code == 405
    assert client.post(_reactivar(proveedor)).status_code == 404  # está activo

    dar_de_baja(admin, proveedor)

    assert client.get(_editar(proveedor)).status_code == 404
    assert client.get(_baja(proveedor)).status_code == 404


@pytest.mark.parametrize("quien", ["cajera_alta", "cajera", "duenio"])
def test_cp99_la_cajera_y_los_duenios_reciben_403(client, request, proveedor, quien):
    client.force_login(request.getfixturevalue(quien))

    for url in (LISTADO, NUEVO, _editar(proveedor), _baja(proveedor)):
        assert client.get(url).status_code == 403, url
    assert client.post(NUEVO, {"nombre": "X"}).status_code == 403
    assert client.post(_baja(proveedor)).status_code == 403
    assert LISTADO not in client.get(reverse("inicio")).content.decode()
    assert Proveedor.objects.count() == 1


def test_el_menu_del_administrador_enlaza_proveedores(client, admin):
    client.force_login(admin)

    assert f'href="{LISTADO}"' in client.get(reverse("inicio")).content.decode()


def test_sin_sesion_redirige_al_ingreso(client):
    assert client.get(LISTADO).url.startswith(reverse("usuarios:ingresar"))


# CP-37: filtro por proveedor de la consulta de stock, por la relación inversa (R-7)


def test_cp37_filtro_por_proveedor_en_productos(client, admin, proveedor, producto, categoria):
    otro_producto = Producto.objects.create(
        nombre="Sin proveedor",
        categoria=categoria,
        precio_venta=Decimal("100"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=True,
    )
    ProductoProveedor.objects.create(producto=producto, proveedor=proveedor, precio_compra=10)
    baja = Proveedor.objects.create(nombre="Dado de baja", activo=False)
    ProductoProveedor.objects.create(producto=otro_producto, proveedor=baja, precio_compra=10)
    client.force_login(admin)

    assert proveedores_para_filtrar() == [(proveedor.pk, proveedor.nombre)]
    respuesta = client.get(reverse("catalogo:productos"), {"proveedor": proveedor.pk})
    assert [p.nombre for p in respuesta.context["pagina"]] == [producto.nombre]
    assert proveedor.nombre in respuesta.content.decode()
