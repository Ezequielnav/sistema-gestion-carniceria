"""CP-74 a CP-76: plantilla base con menú según el rol y resumen del inicio (H1.4)."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.catalogo.services import puede_crear
from apps.comun.menu import FUNCIONES, funciones_para, puede_usar
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db


def _usuario(rol, **extra):
    return Usuario.objects.create_user(
        username=f"u-{rol.lower()}",
        password="clave-de-prueba-123",
        nombre_completo="Usuario de prueba",
        rol=rol,
        **extra,
    )


def _nombres(usuario):
    return [f.nombre for f in funciones_para(usuario)]


# CP-74


@pytest.mark.parametrize("con_permiso", [True, False])
def test_dec103_toda_cajera_ve_productos_y_el_alta_sigue_con_permiso(con_permiso):
    cajera = _usuario(Rol.CAJERA, puede_crear_productos=con_permiso)
    productos = next(f for f in FUNCIONES if f.nombre == "Productos")

    assert puede_usar(cajera, productos)
    assert puede_crear(cajera) is con_permiso


def test_cp74_administrador_ve_todo_salvo_lo_exclusivo_de_la_cajera():
    assert _nombres(_usuario(Rol.ADMINISTRADOR)) == [
        "Historial de ventas",  # DEC-86; anular, DEC-45
        "Productos",  # con la consulta de stock (DEC-105)
        "Clientes",
        "Proveedores",
        "Reportes",
        "Usuarios",
    ]


@pytest.mark.parametrize("con_permiso", [True, False])
def test_cp74_cajera_ve_ventas_ventas_de_la_caja_caja_y_productos(con_permiso):
    # DEC-84: "Ventas de la caja" sin anular. DEC-103: productos con o sin permiso de alta.
    assert _nombres(_usuario(Rol.CAJERA, puede_crear_productos=con_permiso)) == [
        "Ventas",
        "Ventas de la caja",
        "Caja",
        "Productos",
    ]


def test_cp74_duenio_solo_ve_reportes():
    assert _nombres(_usuario(Rol.DUENIO)) == ["Reportes"]


def test_cp74_el_inicio_muestra_solo_el_menu_del_rol(client):
    client.force_login(_usuario(Rol.DUENIO))

    respuesta = client.get(reverse("inicio"))

    assert respuesta.status_code == 200
    assert [f.nombre for f in respuesta.context["menu"]] == ["Reportes"]
    assert "Cobrar en el mostrador" not in respuesta.content.decode()


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.CAJERA, Rol.DUENIO])
def test_el_titulo_del_menu_lateral_es_menu_para_todos_los_roles(client, rol):
    client.force_login(_usuario(rol))

    contenido = client.get(reverse("inicio")).content.decode()

    assert '<nav aria-label="Menú"' in contenido
    assert ">Menú</p>" in contenido
    assert "Funciones" not in contenido


# CP-37 (DEC-30, DEC-82, DEC-105): tarjeta "stock bajo" solo para el Administrador


def test_cp37_la_tarjeta_de_stock_bajo_es_del_administrador_y_lleva_al_filtro(client, producto):
    producto.stock_actual = 0
    producto.save()
    enlace = f"{reverse('catalogo:productos')}?stock_bajo=1"

    client.force_login(_usuario(Rol.ADMINISTRADOR))
    respuesta = client.get(reverse("inicio"))
    assert respuesta.context["stock_bajo"] == 1
    assert enlace in respuesta.content.decode()

    for rol in (Rol.CAJERA, Rol.DUENIO):
        client.force_login(_usuario(rol))
        respuesta = client.get(reverse("inicio"))
        assert respuesta.context["stock_bajo"] is None
        assert enlace not in respuesta.content.decode()


# CP-75


def test_cp75_el_inicio_pide_sesion(client):
    respuesta = client.get(reverse("inicio"))

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(reverse("usuarios:ingresar"))


# CP-76


def test_cp76_el_inicio_resume_el_dia_con_datos_de_la_base(client, venta, producto):
    client.force_login(_usuario(Rol.ADMINISTRADOR))

    respuesta = client.get(reverse("inicio"))

    assert respuesta.context["cantidad_ventas"] == 1
    assert respuesta.context["total_ventas"] == Decimal("2500.00")
    assert respuesta.context["cajas_abiertas"] == [venta.caja]
    assert respuesta.context["productos_activos"] == 1
    assert respuesta.context["ultimas_ventas"] == [venta]


def test_cp76_las_ventas_de_otro_dia_no_suman_hoy(client, venta):
    venta.fecha_hora = timezone.now() - datetime.timedelta(days=1)
    venta.save()
    client.force_login(_usuario(Rol.ADMINISTRADOR))

    respuesta = client.get(reverse("inicio"))

    assert respuesta.context["cantidad_ventas"] == 0
    assert respuesta.context["total_ventas"] == Decimal("0.00")
