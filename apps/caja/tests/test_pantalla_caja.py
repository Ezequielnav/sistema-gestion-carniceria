"""CU-02 de punta a punta: pantalla /caja/ (CP-01, CP-02, CP-07, CP-79, CP-80)."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import Caja, EstadoCaja, Turno
from apps.caja.services import abrir_caja
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

CAJA = reverse("caja:caja")


def _cerrar(caja):
    caja.estado = EstadoCaja.CERRADA
    caja.cerrada_en = timezone.now()
    caja.save()


def _turnos(respuesta):
    return [valor for valor, _ in respuesta.context["form"].fields["turno"].choices]


@pytest.fixture
def cajera_alta(db):
    return Usuario.objects.create_user(
        username="cajera_alta",
        password="clave-de-prueba-123",
        nombre_completo="Cajera Alta",
        rol=Rol.CAJERA,
        puede_crear_productos=True,
    )


# Apertura (RF-04, RF-10, DEC-38)


def test_cp01_la_cajera_abre_la_caja_y_ve_su_estado(client, usuario):
    client.force_login(usuario)

    respuesta = client.post(CAJA, {"turno": Turno.MANANA, "monto_inicial": "5000"})

    assert respuesta.url == CAJA
    caja = Caja.objects.get()
    assert caja.turno == Turno.MANANA and caja.monto_inicial == Decimal("5000")
    contenido = client.get(CAJA).content.decode()
    assert "Abierta" in contenido and "Cajera Uno" in contenido
    assert "Se abrió la caja del turno mañana." in contenido


def test_cp07_sin_fondo_se_guarda_cero(client, usuario):
    client.force_login(usuario)

    client.post(CAJA, {"turno": Turno.TARDE, "monto_inicial": ""})

    assert Caja.objects.get().monto_inicial == Decimal("0")


def test_la_cajera_con_permiso_de_alta_tambien_abre(client, cajera_alta):
    client.force_login(cajera_alta)

    client.post(CAJA, {"turno": Turno.MANANA})

    assert Caja.objects.get().usuario == cajera_alta


def test_el_formulario_arranca_sin_turno_elegido(client, usuario):
    client.force_login(usuario)

    respuesta = client.get(CAJA)

    assert respuesta.context["form"].fields["turno"].choices[0] == ("", "Elegí un turno")
    assert _turnos(respuesta) == ["", Turno.MANANA, Turno.TARDE]
    assert 'min="0"' in respuesta.content.decode()


# Errores junto al campo (CU-02 A1, RI-16)


def test_fondo_negativo_muestra_el_mensaje_junto_al_campo(client, usuario):
    client.force_login(usuario)

    respuesta = client.post(CAJA, {"turno": Turno.MANANA, "monto_inicial": "-1"})

    assert respuesta.status_code == 200
    assert respuesta.context["form"].errors == {"monto_inicial": ["No puede ser negativo."]}
    assert not Caja.objects.exists()


def test_sin_turno_no_se_abre(client, usuario):
    client.force_login(usuario)

    respuesta = client.post(CAJA, {"turno": ""})

    assert "turno" in respuesta.context["form"].errors
    assert not Caja.objects.exists()


# Turnos que se pueden abrir (DEC-39)


def test_cp80_con_la_manana_cerrada_solo_se_ofrece_la_tarde(client, usuario):
    _cerrar(abrir_caja(usuario, Turno.MANANA))
    client.force_login(usuario)

    respuesta = client.get(CAJA)
    assert _turnos(respuesta) == ["", Turno.TARDE]

    respuesta = client.post(CAJA, {"turno": Turno.MANANA})
    assert "turno" in respuesta.context["form"].errors
    assert Caja.objects.count() == 1


def test_con_los_dos_turnos_usados_no_se_muestra_el_formulario(client, usuario):
    _cerrar(abrir_caja(usuario, Turno.MANANA))
    _cerrar(abrir_caja(usuario, Turno.TARDE))
    client.force_login(usuario)

    respuesta = client.get(CAJA)

    assert respuesta.context["form"] is None
    assert "Ya se usaron los dos turnos de hoy." in respuesta.content.decode()


# Una sola caja abierta (CP-02, CP-79, DEC-39)


def test_cp79_con_una_caja_abierta_no_se_muestra_el_formulario_ni_se_abre_otra(client, usuario):
    abrir_caja(usuario, Turno.MANANA)
    client.force_login(usuario)

    respuesta = client.post(CAJA, {"turno": Turno.TARDE})

    assert respuesta.context["form"] is None
    assert Caja.objects.count() == 1


def test_una_caja_abierta_de_otro_dia_pide_cerrarla(client, usuario, caja):
    client.force_login(usuario)

    contenido = client.get(CAJA).content.decode()

    assert "Esta caja es de otro día." in contenido


# Permisos (RF-02, RNF-06)


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_administrador_y_duenios_no_acceden(client, rol):
    otro = Usuario.objects.create_user(
        username="otro", password="clave-de-prueba-123", nombre_completo="Otro", rol=rol
    )
    client.force_login(otro)

    assert client.get(CAJA).status_code == 403
    assert client.post(CAJA, {"turno": Turno.MANANA}).status_code == 403
    assert not Caja.objects.exists()


def test_sin_sesion_redirige_al_ingreso(client):
    respuesta = client.get(CAJA)

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(reverse("usuarios:ingresar"))


def test_el_menu_de_la_cajera_enlaza_caja(client, usuario):
    client.force_login(usuario)

    assert f'href="{CAJA}"' in client.get(reverse("inicio")).content.decode()
