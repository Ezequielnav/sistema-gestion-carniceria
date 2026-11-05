"""CP-124 y CP-125: CU-14 Gestionar usuarios (DEC-135, DEC-149 a DEC-151, DEC-156)."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse

from apps.usuarios.models import Rol, Usuario
from apps.usuarios.services import (
    crear_usuario,
    desactivar,
    modificar_usuario,
    restablecer_contrasena,
)

pytestmark = pytest.mark.django_db

CLAVE = "clave-de-prueba-123"
CLAVE_NUEVA = "otra-clave-segura-456"


def _crear(username, rol, **extra):
    return Usuario.objects.create_user(
        username=username, password=CLAVE, nombre_completo=f"Persona {username}", rol=rol, **extra
    )


@pytest.fixture
def admin(db):
    return _crear("admin1", Rol.ADMINISTRADOR)


@pytest.fixture
def cliente_admin(client, admin):
    client.force_login(admin)
    return client


def _datos(**cambios):
    datos = {
        "username": "marta",
        "nombre_completo": "Marta Gómez",
        "telefono": "",
        "email": "",
        "rol": Rol.CAJERA,
        "puede_crear_productos": True,
        "password1": CLAVE_NUEVA,
        "password2": CLAVE_NUEVA,
    }
    datos.update(cambios)
    return datos


def _datos_de(usuario, **cambios):
    datos = {
        "username": usuario.username,
        "nombre_completo": usuario.nombre_completo,
        "telefono": usuario.telefono,
        "email": usuario.email,
        "rol": usuario.rol,
        "puede_crear_productos": usuario.puede_crear_productos,
    }
    datos.update(cambios)
    return datos


# CP-124: alta, edición, desactivación, reactivación y contraseña


def test_cp124_el_administrador_da_de_alta_una_cajera_que_ingresa_con_su_clave(
    cliente_admin, client
):
    respuesta = cliente_admin.post(reverse("usuarios:nuevo"), _datos())

    assert respuesta.status_code == 302
    marta = Usuario.objects.get(username="marta")
    assert marta.rol == Rol.CAJERA and marta.puede_crear_productos
    assert marta.check_password(CLAVE_NUEVA)
    client.logout()
    assert client.login(username="marta", password=CLAVE_NUEVA)


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_cp124_un_usuario_de_cu14_no_entra_al_panel_y_solo_la_cajera_crea_productos(
    cliente_admin, rol
):
    cliente_admin.post(reverse("usuarios:nuevo"), _datos(rol=rol))

    nuevo = Usuario.objects.get(username="marta")
    # DEC-150: los Administradores de CU-14 no entran al panel; RN-05: solo la cajera.
    assert not nuevo.is_staff and not nuevo.is_superuser
    assert not nuevo.puede_crear_productos


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"password1": "12345678", "password2": "12345678"}, "password1"),
        ({"password2": "distinta-clave-789"}, "password2"),
        ({"username": "admin1"}, "username"),
        ({"rol": ""}, "rol"),
    ],
)
def test_cp124_el_alta_rechaza_datos_invalidos(cliente_admin, cambios, campo):
    respuesta = cliente_admin.post(reverse("usuarios:nuevo"), _datos(**cambios))

    assert respuesta.status_code == 200
    assert respuesta.context["form"].errors.get(campo)
    assert Usuario.objects.count() == 1  # solo el Administrador que da el alta


def test_cp124_editar_cambia_datos_y_rol_sin_tocar_la_contrasena(cliente_admin):
    cajera = _crear("cajera", Rol.CAJERA, puede_crear_productos=True)

    cliente_admin.post(
        reverse("usuarios:editar", args=[cajera.pk]),
        _datos_de(cajera, nombre_completo="Clara Nueva", rol=Rol.DUENIO),
    )

    cajera.refresh_from_db()
    assert cajera.nombre_completo == "Clara Nueva"
    assert cajera.rol == Rol.DUENIO
    assert not cajera.puede_crear_productos
    assert cajera.check_password(CLAVE)


def test_cp124_desactivar_impide_ingresar_y_corta_la_sesion_abierta(cliente_admin, client):
    cajera = _crear("cajera", Rol.CAJERA)
    sesion_cajera = Client()
    sesion_cajera.force_login(cajera)
    assert sesion_cajera.get(reverse("inicio")).status_code == 200

    respuesta = cliente_admin.post(reverse("usuarios:baja", args=[cajera.pk]))

    assert respuesta.status_code == 302
    cajera.refresh_from_db()
    assert not cajera.is_active
    # DEC-151: la sesión abierta deja de valer en el próximo pedido.
    assert sesion_cajera.get(reverse("inicio")).status_code == 302
    assert not Client().login(username="cajera", password=CLAVE)
    assert Usuario.objects.filter(pk=cajera.pk).exists()


def test_cp124_un_desactivado_no_se_edita_y_se_reactiva(cliente_admin):
    cajera = _crear("cajera", Rol.CAJERA, is_active=False)

    assert cliente_admin.get(reverse("usuarios:editar", args=[cajera.pk])).status_code == 404
    listado = cliente_admin.get(reverse("usuarios:usuarios"))
    assert cajera not in listado.context["pagina"].object_list
    listado = cliente_admin.get(reverse("usuarios:usuarios") + "?inactivos=1")
    assert cajera in listado.context["pagina"].object_list

    cliente_admin.post(reverse("usuarios:reactivar", args=[cajera.pk]))

    cajera.refresh_from_db()
    assert cajera.is_active


def test_cp124_restablecer_la_contrasena(cliente_admin, client):
    cajera = _crear("cajera", Rol.CAJERA)

    respuesta = cliente_admin.post(
        reverse("usuarios:contrasena", args=[cajera.pk]),
        {"password1": CLAVE_NUEVA, "password2": CLAVE_NUEVA},
    )

    assert respuesta.status_code == 302
    cajera.refresh_from_db()
    assert cajera.check_password(CLAVE_NUEVA)
    assert not cajera.check_password(CLAVE)


def test_cp124_cambiar_la_propia_contrasena_no_cierra_la_sesion(cliente_admin, admin):
    cliente_admin.post(
        reverse("usuarios:contrasena", args=[admin.pk]),
        {"password1": CLAVE_NUEVA, "password2": CLAVE_NUEVA},
    )

    assert cliente_admin.get(reverse("usuarios:usuarios")).status_code == 200


def test_cp124_el_listado_busca_por_usuario_o_nombre(cliente_admin):
    _crear("cajera", Rol.CAJERA)

    listado = cliente_admin.get(reverse("usuarios:usuarios") + "?q=persona cajera")

    assert [u.username for u in listado.context["pagina"].object_list] == ["cajera"]


@pytest.mark.parametrize("rol", [Rol.CAJERA, Rol.DUENIO])
def test_cp124_solo_el_administrador_gestiona_usuarios(client, rol):
    otro = _crear("otro", rol)
    client.force_login(otro)

    assert client.get(reverse("usuarios:usuarios")).status_code == 403
    assert client.post(reverse("usuarios:nuevo"), _datos()).status_code == 403
    with pytest.raises(PermissionDenied):
        crear_usuario(otro, _datos(), CLAVE_NUEVA)
    assert not Usuario.objects.filter(username="marta").exists()


# CP-125: siempre queda un Administrador activo; nadie se desactiva ni se quita el rol


def test_cp125_el_administrador_no_se_desactiva_ni_se_quita_el_rol(cliente_admin, admin):
    respuesta = cliente_admin.post(reverse("usuarios:baja", args=[admin.pk]))
    assert "No podés desactivar tu propio usuario." in respuesta.content.decode()

    respuesta = cliente_admin.post(
        reverse("usuarios:editar", args=[admin.pk]), _datos_de(admin, rol=Rol.CAJERA)
    )
    assert respuesta.context["form"].errors["rol"] == ["No podés cambiar tu propio rol."]

    admin.refresh_from_db()
    assert admin.is_active and admin.rol == Rol.ADMINISTRADOR


def test_cp125_no_queda_el_sistema_sin_administrador_activo(admin):
    otro = _crear("admin2", Rol.ADMINISTRADOR)
    desactivar(admin, otro)

    # "otro" ya está desactivado: si su pedido llega después (dos Administradores al mismo
    # tiempo), no puede dejar al sistema sin ninguno.
    with pytest.raises(ValidationError, match="al menos un Administrador activo"):
        desactivar(otro, admin)
    with pytest.raises(ValidationError, match="al menos un Administrador activo"):
        modificar_usuario(otro, admin, _datos_de(admin, rol=Rol.CAJERA))

    admin.refresh_from_db()
    assert admin.is_active and admin.rol == Rol.ADMINISTRADOR


# DEC-156: CU-14 no toca al superusuario técnico


def test_dec156_cu14_no_cambia_rol_estado_ni_clave_de_un_usuario_con_panel(cliente_admin, admin):
    tecnico = Usuario.objects.create_superuser(
        username="tecnico", password=CLAVE, nombre_completo="Técnico", rol=Rol.ADMINISTRADOR
    )

    with pytest.raises(ValidationError, match="manage.py"):
        desactivar(admin, tecnico)
    with pytest.raises(ValidationError, match="manage.py"):
        restablecer_contrasena(admin, tecnico, CLAVE_NUEVA)
    respuesta = cliente_admin.post(
        reverse("usuarios:editar", args=[tecnico.pk]), _datos_de(tecnico, rol=Rol.CAJERA)
    )
    assert "manage.py" in respuesta.context["form"].errors["rol"][0]

    # Sus otros datos sí se editan.
    cliente_admin.post(
        reverse("usuarios:editar", args=[tecnico.pk]),
        _datos_de(tecnico, nombre_completo="Soporte técnico"),
    )
    tecnico.refresh_from_db()
    assert tecnico.nombre_completo == "Soporte técnico"
    assert tecnico.is_active and tecnico.is_superuser and tecnico.check_password(CLAVE)
