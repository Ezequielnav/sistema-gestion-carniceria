"""CU-02: reglas de apps/caja/services.py (CP-01, CP-02, CP-07, CP-79, CP-80)."""

from decimal import Decimal
from unittest import mock

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.caja.models import Caja, EstadoCaja, Turno
from apps.caja.services import (
    abrir_caja,
    caja_abierta,
    caja_cerrada,
    es_de_otro_dia,
    turnos_libres,
)
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db


def _cerrar(caja):
    caja.estado = EstadoCaja.CERRADA
    caja.cerrada_en = timezone.now()
    caja.save()


def _mensajes(error):
    return " ".join(error.value.messages)


# CP-01 y CP-07 (RF-04, RF-10, DEC-38)


def test_cp01_abre_la_caja_de_hoy_en_el_turno_elegido(usuario):
    caja = abrir_caja(usuario, Turno.MANANA)

    assert caja.estado == EstadoCaja.ABIERTA
    assert caja.fecha == timezone.localdate()
    assert caja.turno == Turno.MANANA
    assert caja.usuario == usuario
    assert caja.abierta_en is not None
    assert caja_abierta() == caja


def test_cp07_abre_con_fondo_de_cambio(usuario):
    assert abrir_caja(usuario, Turno.MANANA, Decimal("5000.00")).monto_inicial == Decimal("5000")


def test_cp07_el_fondo_vacio_se_guarda_cero(usuario):
    caja = abrir_caja(usuario, Turno.MANANA, None)

    caja.refresh_from_db()
    assert caja.monto_inicial == Decimal("0")


def test_el_fondo_negativo_se_rechaza(usuario):
    with pytest.raises(ValidationError) as error:
        abrir_caja(usuario, Turno.MANANA, Decimal("-1"))

    assert error.value.message_dict == {"monto_inicial": ["No puede ser negativo."]}
    assert not Caja.objects.exists()


def test_cp03_un_turno_invalido_se_rechaza(usuario):
    with pytest.raises(ValidationError) as error:
        abrir_caja(usuario, "NOCHE")

    assert "turno" in error.value.message_dict


# CP-02 y CP-79 (RF-05, RN-01, DEC-39)


def test_cp02_con_una_caja_abierta_no_se_abre_otra_del_mismo_turno(usuario):
    abrir_caja(usuario, Turno.MANANA)

    with pytest.raises(ValidationError) as error:
        abrir_caja(usuario, Turno.MANANA)

    assert "Ya hay una caja abierta: la del turno mañana" in _mensajes(error)
    assert Caja.objects.count() == 1


def test_cp79_con_la_manana_abierta_no_se_abre_la_tarde(usuario):
    abrir_caja(usuario, Turno.MANANA)

    with pytest.raises(ValidationError) as error:
        abrir_caja(usuario, Turno.TARDE)

    assert "Hay que cerrarla antes de abrir otra" in _mensajes(error)


def test_una_caja_abierta_de_otro_dia_impide_abrir_hoy(caja, usuario):
    with pytest.raises(ValidationError) as error:
        abrir_caja(usuario, Turno.TARDE)

    assert caja.fecha.strftime("%d/%m/%Y") in _mensajes(error)


# CP-80 (DEC-39)


def test_cp80_un_turno_cerrado_no_se_reabre_el_mismo_dia(usuario):
    _cerrar(abrir_caja(usuario, Turno.MANANA))

    with pytest.raises(ValidationError) as error:
        abrir_caja(usuario, Turno.MANANA)

    assert error.value.message_dict == {
        "turno": ["El turno mañana ya tuvo una caja hoy y no se reabre."]
    }


def test_cp80_con_la_manana_cerrada_se_abre_la_tarde(usuario):
    _cerrar(abrir_caja(usuario, Turno.MANANA))

    assert abrir_caja(usuario, Turno.TARDE).turno == Turno.TARDE


def test_turnos_libres_del_dia(usuario):
    hoy = timezone.localdate()
    assert turnos_libres(hoy) == [Turno.MANANA, Turno.TARDE]

    _cerrar(abrir_caja(usuario, Turno.MANANA))
    assert turnos_libres(hoy) == [Turno.TARDE]

    _cerrar(abrir_caja(usuario, Turno.TARDE))
    assert turnos_libres(hoy) == []


# Apertura simultánea (RI-01): la base decide y el mensaje es el mismo


def test_dos_cajeras_a_la_vez_la_segunda_recibe_el_mensaje_claro(usuario):
    otra = abrir_caja(usuario, Turno.MANANA)

    # Simula que la verificación previa no vio la caja que la otra cajera acababa de abrir.
    with (
        mock.patch("apps.caja.services.caja_abierta", side_effect=[None, otra]),
        pytest.raises(ValidationError) as error,
    ):
        abrir_caja(usuario, Turno.TARDE)

    assert "Ya hay una caja abierta" in _mensajes(error)
    assert Caja.objects.count() == 1


def test_si_la_caja_que_choco_ya_no_esta_abierta_el_mensaje_no_falla(usuario):
    abrir_caja(usuario, Turno.MANANA)

    # La segunda consulta ya no encuentra la caja con la que chocó (se cerró entre medio).
    with (
        mock.patch("apps.caja.services.caja_abierta", side_effect=[None, None]),
        pytest.raises(ValidationError) as error,
    ):
        abrir_caja(usuario, Turno.TARDE)

    assert _mensajes(error) == "Ya hay una caja abierta. Hay que cerrarla antes de abrir otra."
    assert Caja.objects.count() == 1


def test_turno_usado_a_la_vez_recibe_el_mensaje_claro(usuario):
    _cerrar(abrir_caja(usuario, Turno.MANANA))

    with (
        mock.patch("apps.caja.services.turnos_libres", return_value=list(Turno)),
        pytest.raises(ValidationError) as error,
    ):
        abrir_caja(usuario, Turno.MANANA)

    assert error.value.message_dict == {
        "turno": ["El turno mañana ya tuvo una caja hoy y no se reabre."]
    }
    assert Caja.objects.count() == 1


# Permisos (matriz de actores de 04)


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_solo_la_cajera_abre_la_caja(rol):
    otro = Usuario.objects.create_user(
        username="otro", password="clave-de-prueba-123", nombre_completo="Otro", rol=rol
    )

    with pytest.raises(PermissionDenied):
        abrir_caja(otro, Turno.MANANA)


# Capas (06): consultas y reglas que antes estaban en la vista


def test_caja_cerrada_solo_devuelve_cajas_cerradas(usuario):
    caja = abrir_caja(usuario, Turno.MANANA)
    with pytest.raises(Caja.DoesNotExist):
        caja_cerrada(caja.pk)

    _cerrar(caja)

    assert caja_cerrada(caja.pk) == caja
    with pytest.raises(Caja.DoesNotExist):
        caja_cerrada(999999)


def test_dec50_es_de_otro_dia(usuario, caja):
    assert es_de_otro_dia(caja) is True  # la caja del conftest es del 15/01/2026
    _cerrar(caja)

    assert es_de_otro_dia(abrir_caja(usuario, Turno.MANANA)) is False
