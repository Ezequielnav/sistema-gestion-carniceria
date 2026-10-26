"""Etapa 3 de H2 de punta a punta: egreso, cierre y reporte de cierre (CP-04 a CP-07, CP-81)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.caja.models import Caja, EstadoCaja, MedioPago, MovimientoCaja, Turno
from apps.caja.services import abrir_caja, cerrar_caja, registrar_egreso_otro
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

CAJA = reverse("caja:caja")
EGRESO = reverse("caja:egreso")
CERRAR = reverse("caja:cerrar")


@pytest.fixture
def tarjeta(db):
    return MedioPago.objects.create(nombre="Tarjeta")


@pytest.fixture
def caja_hoy(usuario, efectivo, tarjeta):
    return abrir_caja(usuario, Turno.MANANA, Decimal("5000"))


def _otro(rol):
    return Usuario.objects.create_user(
        username=f"u-{rol.lower()}", password="clave-de-prueba-123", nombre_completo="Otro", rol=rol
    )


def _cierre(caja):
    return reverse("caja:cierre", args=[caja.pk])


# Egresos "otros" (CP-81, DEC-58)


def test_cp81_registrar_egreso_desde_la_pantalla_y_verlo_en_la_lista(client, usuario, caja_hoy):
    client.force_login(usuario)

    respuesta = client.post(EGRESO, {"monto": "2000", "descripcion": "Retiro para el dueño"})

    assert respuesta.url == CAJA
    contenido = client.get(CAJA).content.decode()
    assert "Se registró el egreso." in contenido
    assert "Retiro para el dueño" in contenido and "$ 2.000,00" in contenido


def test_egreso_sin_descripcion_muestra_el_error_junto_al_campo(client, usuario, caja_hoy):
    client.force_login(usuario)

    respuesta = client.post(EGRESO, {"monto": "100", "descripcion": ""})

    assert respuesta.status_code == 200
    assert "descripcion" in respuesta.context["egreso_form"].errors
    assert not MovimientoCaja.objects.exists()


def test_dec57_egreso_mayor_al_efectivo_muestra_el_aviso(client, usuario, caja_hoy):
    client.force_login(usuario)

    respuesta = client.post(EGRESO, {"monto": "9000", "descripcion": "Retiro"})

    assert respuesta.context["egreso_form"].errors == {
        "monto": ["En la caja hay $ 5000.00 en efectivo: no alcanza."]
    }


def test_egreso_sin_caja_abierta_vuelve_a_caja(client, usuario):
    client.force_login(usuario)

    respuesta = client.post(EGRESO, {"monto": "10", "descripcion": "Bolsas"})

    assert respuesta.url == CAJA
    assert not MovimientoCaja.objects.exists()


# Cierre (CP-04, CP-06, CP-07, RF-07, RF-08)


def test_cp07_el_cierre_muestra_lo_esperado_por_medio(client, usuario, caja_hoy, efectivo):
    registrar_egreso_otro(usuario, Decimal("1000"), "Bolsas")
    client.force_login(usuario)

    respuesta = client.get(CERRAR)

    filas = {medio.nombre: esperado for medio, esperado, _ in respuesta.context["form"].filas()}
    assert filas == {"Efectivo": Decimal("4000"), "Tarjeta": Decimal("0")}
    assert "Incluye el fondo de cambio" in respuesta.content.decode()


def test_cp04_cerrar_sin_diferencias_y_ver_el_reporte(client, usuario, caja_hoy, efectivo, tarjeta):
    client.force_login(usuario)

    respuesta = client.post(
        CERRAR, {f"contado_{efectivo.pk}": "5000", f"contado_{tarjeta.pk}": "0", "observacion": ""}
    )

    caja_hoy.refresh_from_db()
    assert caja_hoy.estado == EstadoCaja.CERRADA
    assert respuesta.url == _cierre(caja_hoy)
    contenido = client.get(respuesta.url).content.decode()
    for texto in [
        "Cierre de caja",
        "Cerró: Cajera Uno",
        "Sin diferencias.",
        "Imprimir",
        "Ir a Caja",
    ]:
        assert texto in contenido, texto


def test_cp06_con_diferencia_pide_motivo_y_despues_cierra(
    client, usuario, caja_hoy, efectivo, tarjeta
):
    client.force_login(usuario)
    datos = {f"contado_{efectivo.pk}": "4800", f"contado_{tarjeta.pk}": "0", "observacion": ""}

    respuesta = client.post(CERRAR, datos)
    assert respuesta.status_code == 200
    assert respuesta.context["form"].errors == {
        "observacion": ["Hay diferencias: escribí el motivo para poder cerrar."]
    }
    caja_hoy.refresh_from_db()
    assert caja_hoy.estado == EstadoCaja.ABIERTA

    respuesta = client.post(CERRAR, {**datos, "observacion": "Vuelto mal dado"})
    contenido = client.get(respuesta.url).content.decode()
    assert "Vuelto mal dado" in contenido and "$ -200,00" in contenido


def test_contado_vacio_o_negativo_muestra_el_error_junto_al_campo(
    client, usuario, caja_hoy, efectivo, tarjeta
):
    client.force_login(usuario)

    respuesta = client.post(CERRAR, {f"contado_{efectivo.pk}": "", f"contado_{tarjeta.pk}": "-1"})

    errores = respuesta.context["form"].errors
    assert errores[f"contado_{efectivo.pk}"] == ["Falta lo contado en Efectivo."]
    assert errores[f"contado_{tarjeta.pk}"] == ["No puede ser negativo."]
    assert Caja.objects.get().estado == EstadoCaja.ABIERTA


def test_cerrar_sin_caja_abierta_vuelve_a_caja(client, usuario):
    client.force_login(usuario)

    assert client.get(CERRAR).url == CAJA


def test_la_pantalla_de_caja_ofrece_cerrar(client, usuario, caja_hoy):
    client.force_login(usuario)

    assert f'href="{CERRAR}"' in client.get(CAJA).content.decode()


# Reporte de cierre (DEC-59, DEC-60)


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_dec59_administrador_y_duenios_ven_el_reporte(client, rol, usuario, caja_hoy, efectivo):
    cerrar_caja(
        usuario,
        {efectivo.pk: Decimal("5000"), MedioPago.objects.get(nombre="Tarjeta").pk: Decimal("0")},
    )
    client.force_login(_otro(rol))

    contenido = client.get(_cierre(caja_hoy)).content.decode()

    assert "Cierre de caja" in contenido and "Volver al inicio" in contenido


def test_el_reporte_de_una_caja_abierta_no_existe(client, usuario, caja_hoy):
    client.force_login(usuario)

    assert client.get(_cierre(caja_hoy)).status_code == 404


def test_el_reporte_pide_sesion(client, caja_hoy):
    respuesta = client.get(_cierre(caja_hoy))

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(reverse("usuarios:ingresar"))


# Permisos (RF-02, RNF-06)


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_administrador_y_duenios_no_cierran_ni_registran_egresos(
    client, rol, caja_hoy, efectivo, tarjeta
):
    client.force_login(_otro(rol))

    assert client.get(CERRAR).status_code == 403
    assert client.post(CERRAR, {f"contado_{efectivo.pk}": "5000"}).status_code == 403
    assert client.post(EGRESO, {"monto": "10", "descripcion": "Bolsas"}).status_code == 403
    assert Caja.objects.get().estado == EstadoCaja.ABIERTA
    assert not MovimientoCaja.objects.exists()
