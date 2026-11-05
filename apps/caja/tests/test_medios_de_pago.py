"""CP-137: medios de pago fuera del panel, solo del Administrador (DEC-155, L18)."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.caja.models import MedioPago
from apps.caja.services import cambiar_activo, crear_medio
from apps.usuarios.models import Rol, Usuario
from apps.ventas.services import medios_de_pago_para_venta

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        username="admin",
        password="clave-de-prueba-123",
        nombre_completo="Admin",
        rol=Rol.ADMINISTRADOR,
    )


@pytest.fixture
def cliente_admin(client, admin):
    client.force_login(admin)
    return client


def test_cp137_alta_de_un_medio_que_ingresa_a_caja(cliente_admin):
    respuesta = cliente_admin.post(
        reverse("caja:medio_nuevo"), {"nombre": " Tarjeta de débito ", "ingresa_a_caja": "on"}
    )

    assert respuesta.status_code == 302
    medio = MedioPago.objects.get(nombre="Tarjeta de débito")
    assert medio.activo and medio.ingresa_a_caja and not medio.es_efectivo


@pytest.mark.parametrize(
    ("datos", "mensaje"),
    [
        (
            {"nombre": "EFECTIVO", "ingresa_a_caja": "on"},
            "Ya existe un medio de pago con ese nombre.",
        ),
        (
            {"nombre": "Pesos", "ingresa_a_caja": "on", "es_efectivo": "on"},
            "Ya hay otro medio de pago marcado como efectivo.",
        ),
        ({"nombre": "Fiado"}, "Ya hay otro medio de pago que no ingresa a caja."),
        ({"nombre": "Caja chica", "es_efectivo": "on"}, "El efectivo ingresa a caja."),
    ],
)
def test_cp137_el_alta_respeta_las_reglas_de_los_medios(cliente_admin, efectivo, datos, mensaje):
    MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)

    respuesta = cliente_admin.post(reverse("caja:medio_nuevo"), datos)

    assert respuesta.status_code == 200
    assert mensaje in respuesta.content.decode()
    assert MedioPago.objects.count() == 2


def test_cp137_editar_cambia_solo_el_nombre(cliente_admin, efectivo):
    cliente_admin.post(
        reverse("caja:medio_editar", args=[efectivo.pk]),
        {"nombre": "Efectivo en pesos", "es_efectivo": "", "ingresa_a_caja": ""},
    )

    efectivo.refresh_from_db()
    assert efectivo.nombre == "Efectivo en pesos"
    assert efectivo.es_efectivo and efectivo.ingresa_a_caja


def test_cp137_desactivar_y_activar_sin_borrar(cliente_admin):
    qr = MedioPago.objects.create(nombre="QR")
    url = reverse("caja:medio_activo", args=[qr.pk])

    cliente_admin.post(url, {"activo": "0"})
    qr.refresh_from_db()
    assert not qr.activo
    assert qr not in medios_de_pago_para_venta()

    cliente_admin.post(url, {"activo": "1"})
    qr.refresh_from_db()
    assert qr.activo
    assert MedioPago.objects.filter(pk=qr.pk).exists()


def test_cp137_el_efectivo_no_se_desactiva(cliente_admin, admin, efectivo):
    respuesta = cliente_admin.post(
        reverse("caja:medio_activo", args=[efectivo.pk]), {"activo": "0"}, follow=True
    )

    assert "El efectivo no se desactiva" in respuesta.content.decode()
    efectivo.refresh_from_db()
    assert efectivo.activo
    with pytest.raises(ValidationError):
        cambiar_activo(admin, efectivo, False)


@pytest.mark.parametrize("rol", [Rol.CAJERA, Rol.DUENIO])
def test_cp137_solo_el_administrador_gestiona_medios(client, rol, efectivo):
    otro = Usuario.objects.create_user(
        username="otro", password="clave-de-prueba-123", nombre_completo="Otro", rol=rol
    )
    client.force_login(otro)

    assert client.get(reverse("caja:medios")).status_code == 403
    assert client.post(reverse("caja:medio_nuevo"), {"nombre": "QR"}).status_code == 403
    assert (
        client.post(reverse("caja:medio_activo", args=[efectivo.pk]), {"activo": "0"}).status_code
        == 403
    )
    with pytest.raises(PermissionDenied):
        crear_medio(otro, "QR", True, False)
    efectivo.refresh_from_db()
    assert efectivo.activo and MedioPago.objects.count() == 1
