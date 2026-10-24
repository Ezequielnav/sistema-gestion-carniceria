"""CU-10 Iniciar sesión y permisos por rol: CP-50, CP-52, CP-53, CP-54 y DEC-32."""

import pytest
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.views.defaults import permission_denied

from apps.catalogo.models import Producto
from apps.comun.permisos import requiere_funcion
from apps.usuarios.forms import MENSAJE_GENERICO
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

CLAVE = "clave-de-prueba-123"


def _usuario(rol, **extra):
    return Usuario.objects.create_user(
        username=f"u-{rol.lower()}", password=CLAVE, nombre_completo="Prueba", rol=rol, **extra
    )


def _ingresar(client, username, password=CLAVE):
    return client.post(reverse("usuarios:ingresar"), {"username": username, "password": password})


# CP-50 (RF-01; CU-10 flujo normal, A1 y A2)


@pytest.mark.parametrize("rol", Rol.values)
def test_cp50_cada_rol_entra_con_credenciales_validas(client, rol):
    usuario = _usuario(rol)

    respuesta = _ingresar(client, usuario.username)

    assert respuesta.status_code == 302
    assert respuesta.url == reverse("inicio")
    assert client.session[SESSION_KEY] == str(usuario.pk)


@pytest.mark.parametrize(
    ("username", "password"),
    [("u-cajera", "otra-clave"), ("no-existe", CLAVE), ("", "")],
)
def test_cp50_credenciales_invalidas_no_entran_y_el_mensaje_es_generico(client, username, password):
    _usuario(Rol.CAJERA)

    respuesta = _ingresar(client, username, password)

    assert respuesta.status_code == 200
    assert SESSION_KEY not in client.session
    if username:
        assert MENSAJE_GENERICO in respuesta.content.decode()


def test_cp50_usuario_dado_de_baja_no_entra_con_el_mismo_mensaje(client):
    usuario = _usuario(Rol.CAJERA, is_active=False)

    respuesta = _ingresar(client, usuario.username)

    assert SESSION_KEY not in client.session
    assert MENSAJE_GENERICO in respuesta.content.decode()


def test_cerrar_sesion_termina_la_sesion_y_vuelve_al_ingreso(client):
    client.force_login(_usuario(Rol.CAJERA))

    respuesta = client.post(reverse("usuarios:salir"))

    assert respuesta.url == reverse("usuarios:ingresar")
    assert SESSION_KEY not in client.session
    assert client.get(reverse("inicio")).status_code == 302


def test_cerrar_sesion_no_se_hace_con_un_enlace(client):
    client.force_login(_usuario(Rol.CAJERA))

    assert client.get(reverse("usuarios:salir")).status_code == 405
    assert SESSION_KEY in client.session


def test_con_sesion_iniciada_el_ingreso_lleva_al_inicio(client):
    client.force_login(_usuario(Rol.DUENIO))

    respuesta = client.get(reverse("usuarios:ingresar"))

    assert respuesta.url == reverse("inicio")


# CP-52 (RNF-06)


def test_cp52_sin_sesion_redirige_al_ingreso_y_vuelve_despues(client):
    usuario = _usuario(Rol.CAJERA)

    respuesta = client.get(reverse("inicio"))
    assert respuesta.url == f"{reverse('usuarios:ingresar')}?next=/"

    respuesta = client.post(
        respuesta.url, {"username": usuario.username, "password": CLAVE, "next": "/"}
    )
    assert respuesta.url == "/"


# Permisos de las pantallas: misma tabla que el menú (RF-02)


def _vista(nombre):
    @requiere_funcion(nombre)
    def vista(request):
        return HttpResponse("ok")

    return vista


def _pedir(vista, usuario):
    request = RequestFactory().get("/")
    request.user = usuario
    return vista(request)


def test_cp52_una_pantalla_protegida_pide_sesion():
    respuesta = _pedir(_vista("Reportes"), AnonymousUser())

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(reverse("usuarios:ingresar"))


# CP-53 (RN-06, RF-45): los dueños solo consultan


@pytest.mark.parametrize("funcion", ["Ventas", "Caja", "Productos", "Clientes", "Usuarios"])
def test_cp53_duenio_no_abre_pantallas_que_modifican_datos(funcion):
    with pytest.raises(PermissionDenied):
        _pedir(_vista(funcion), _usuario(Rol.DUENIO))


def test_cp53_duenio_si_abre_reportes():
    assert _pedir(_vista("Reportes"), _usuario(Rol.DUENIO)).status_code == 200


def test_cp53_duenio_no_entra_al_panel_ni_carga_datos(client, categoria):
    client.force_login(_usuario(Rol.DUENIO))

    assert client.get(reverse("admin:index")).status_code == 302
    client.post(
        reverse("admin:catalogo_producto_add"),
        {"nombre": "X", "precio_venta": "1", "unidad_medida": "UNIDAD"},
    )
    assert not Producto.objects.exists()


# CP-54 (RF-02): la cajera no accede a funciones de administrador


@pytest.mark.parametrize("funcion", ["Stock", "Clientes", "Proveedores", "Reportes", "Usuarios"])
def test_cp54_cajera_no_abre_funciones_de_administrador(funcion):
    with pytest.raises(PermissionDenied):
        _pedir(_vista(funcion), _usuario(Rol.CAJERA, puede_crear_productos=True))


def test_cp54_cajera_no_entra_al_panel(client):
    client.force_login(_usuario(Rol.CAJERA))

    assert client.get(reverse("admin:usuarios_usuario_changelist")).status_code == 302


def test_rn05_productos_solo_para_la_cajera_con_permiso():
    vista = _vista("Productos")

    with pytest.raises(PermissionDenied):
        _pedir(vista, _usuario(Rol.CAJERA))
    cajera_alta = Usuario.objects.create_user(
        username="alta",
        password=CLAVE,
        nombre_completo="A",
        rol=Rol.CAJERA,
        puede_crear_productos=True,
    )
    assert _pedir(vista, cajera_alta).status_code == 200


def test_el_administrador_abre_sus_funciones():
    assert _pedir(_vista("Usuarios"), _usuario(Rol.ADMINISTRADOR)).status_code == 200


def test_sin_permiso_se_muestra_una_pagina_clara():
    request = RequestFactory().get("/")
    request.user = _usuario(Rol.CAJERA)

    respuesta = permission_denied(request, PermissionDenied())

    assert respuesta.status_code == 403
    assert "No tenés permiso para esta función" in respuesta.content.decode()


# DEC-32: solo el Administrador accede al panel o es superusuario


@pytest.mark.parametrize("rol", [Rol.CAJERA, Rol.DUENIO])
@pytest.mark.parametrize("acceso", [{"is_staff": True}, {"is_superuser": True}])
def test_dec32_otro_rol_con_acceso_al_panel_se_rechaza(rol, acceso):
    with pytest.raises(IntegrityError), transaction.atomic():
        _usuario(rol, **acceso)


def test_dec32_el_administrador_puede_acceder_al_panel():
    _usuario(Rol.ADMINISTRADOR, is_staff=True, is_superuser=True)
