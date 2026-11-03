"""Historial de ventas del Administrador (CP-98, DEC-86)."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import Caja, EstadoCaja, Turno
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import Venta
from apps.ventas.services import historial_de_ventas

pytestmark = pytest.mark.django_db

HISTORIAL = reverse("ventas:historial")
DIA_1 = datetime.date(2026, 1, 15)
DIA_2 = datetime.date(2026, 1, 16)


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        username="admin1", password="clave-de-prueba-123", rol=Rol.ADMINISTRADOR
    )


def _caja(fecha, turno, usuario, abierta=False):
    return Caja.objects.create(
        fecha=fecha,
        turno=turno,
        usuario=usuario,
        estado=EstadoCaja.ABIERTA if abierta else EstadoCaja.CERRADA,
        cerrada_en=None if abierta else timezone.now(),
    )


def _venta(caja, usuario, medio):
    return Venta.objects.create(
        caja=caja, usuario=usuario, medio_pago=medio, monto_total=Decimal("100.00")
    )


@pytest.fixture
def ventas(usuario, efectivo):
    """Tres cajas cerradas (dos el día 1) y una abierta el día 2, con una venta cada una."""
    cajas = {
        "d1_manana": _caja(DIA_1, Turno.MANANA, usuario),
        "d1_tarde": _caja(DIA_1, Turno.TARDE, usuario),
        "d1_tarde_2": _caja(DIA_1, Turno.TARDE, usuario),  # DEC-83: otra caja en el turno
        "d2_abierta": _caja(DIA_2, Turno.MANANA, usuario, abierta=True),
    }
    return {nombre: _venta(caja, usuario, efectivo) for nombre, caja in cajas.items()}


# Servicio


def test_cp98_por_defecto_trae_la_caja_abierta(ventas):
    resultado, caja = historial_de_ventas()

    assert list(resultado) == [ventas["d2_abierta"]]
    assert caja == ventas["d2_abierta"].caja


def test_cp98_sin_caja_abierta_por_defecto_trae_todas(usuario, efectivo):
    primera = _venta(_caja(DIA_1, Turno.MANANA, usuario), usuario, efectivo)
    segunda = _venta(_caja(DIA_2, Turno.MANANA, usuario), usuario, efectivo)

    resultado, caja = historial_de_ventas()

    assert list(resultado) == [segunda, primera]
    assert caja is None


def test_cp98_todas_ignora_la_caja_abierta(ventas):
    resultado, caja = historial_de_ventas(todas=True)

    assert set(resultado) == set(ventas.values())
    assert caja is None


def test_cp98_filtra_por_fecha_turno_y_caja(ventas):
    assert set(historial_de_ventas(desde=DIA_2)[0]) == {ventas["d2_abierta"]}
    assert set(historial_de_ventas(hasta=DIA_1)[0]) == {
        ventas["d1_manana"],
        ventas["d1_tarde"],
        ventas["d1_tarde_2"],
    }
    assert set(historial_de_ventas(hasta=DIA_1, turno=Turno.TARDE)[0]) == {
        ventas["d1_tarde"],
        ventas["d1_tarde_2"],
    }
    caja = ventas["d1_tarde_2"].caja
    assert list(historial_de_ventas(caja=caja)[0]) == [ventas["d1_tarde_2"]]


# Pantalla


def test_cp98_el_admin_filtra_y_ve_ventas_de_cajas_cerradas(client, admin, ventas):
    client.force_login(admin)

    respuesta = client.get(HISTORIAL, {"desde": "2026-01-15", "hasta": "2026-01-15"})

    assert respuesta.status_code == 200
    assert len(respuesta.context["pagina"].object_list) == 3
    cerrada = ventas["d1_manana"]
    assert client.get(reverse("ventas:detalle", args=[cerrada.pk])).status_code == 200
    assert client.get(reverse("ventas:ticket", args=[cerrada.pk])).status_code == 200


def test_cp98_desde_posterior_a_hasta_muestra_el_error(client, admin, ventas):
    client.force_login(admin)

    respuesta = client.get(HISTORIAL, {"desde": "2026-01-16", "hasta": "2026-01-15"})

    assert "La fecha hasta no puede ser anterior a la fecha desde." in respuesta.content.decode()


def test_cp98_pagina_de_a_25_y_conserva_los_filtros(client, admin, usuario, efectivo):
    caja = _caja(DIA_1, Turno.MANANA, usuario)
    for _ in range(30):
        _venta(caja, usuario, efectivo)
    client.force_login(admin)

    primera = client.get(HISTORIAL, {"todas": "on"})
    segunda = client.get(HISTORIAL, {"todas": "on", "pagina": "2"})

    assert len(primera.context["pagina"].object_list) == 25
    assert "todas=on&amp;pagina=2" in primera.content.decode()
    assert len(segunda.context["pagina"].object_list) == 5


def test_cp98_la_anulacion_sigue_limitada_a_la_caja_abierta(client, admin, ventas):
    client.force_login(admin)
    cerrada = ventas["d1_manana"]

    contenido = client.get(reverse("ventas:detalle", args=[cerrada.pk])).content.decode()
    respuesta = client.post(reverse("ventas:anular", args=[cerrada.pk]), {"motivo": "Prueba"})

    assert "ya no se puede anular" in contenido
    assert respuesta.status_code == 400
    assert "Volver al historial de ventas" in contenido


@pytest.mark.parametrize("rol", [Rol.CAJERA, Rol.DUENIO])
def test_cp98_solo_el_administrador_entra_al_historial(client, rol):
    otro = Usuario.objects.create_user(username="otro", password="clave-de-prueba-123", rol=rol)
    client.force_login(otro)

    assert client.get(HISTORIAL).status_code == 403
