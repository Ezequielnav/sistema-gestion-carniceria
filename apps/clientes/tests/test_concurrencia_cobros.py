"""CP-120: un cobro, o su anulación, y el cierre de la misma caja a la vez no se cruzan
(RNF-10, RI-02, DEC-128). Como CP-88: transacciones reales y dos hilos.
"""

import threading
import time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.caja.models import Caja, CierreCajaDetalle, EstadoCaja, MedioPago, MovimientoCaja, Turno
from apps.caja.services import abrir_caja, cerrar_caja
from apps.clientes.models import (
    Cliente,
    EstadoPagoCliente,
    MovimientoCuentaCorriente,
    PagoCliente,
    TipoMovimientoCuentaCorriente,
)
from apps.clientes.services import anular_cobro, registrar_cobro, saldo
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db(transaction=True)

ESPERA = 0.5  # segundos que la primera operación retiene el bloqueo antes de confirmar


def _usuario(username, rol):
    return Usuario.objects.create_user(
        username=username, password="clave-de-prueba-123", nombre_completo=username, rol=rol
    )


@pytest.fixture
def escenario():
    cajera = _usuario("cajera_cobros", Rol.CAJERA)
    admin = _usuario("admin_cobros", Rol.ADMINISTRADOR)
    efectivo = MedioPago.objects.create(nombre="Efectivo", es_efectivo=True)
    caja = abrir_caja(cajera, Turno.MANANA, Decimal("1000.00"))
    cliente = Cliente.objects.create(nombre="Juan Pérez")
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        tipo=TipoMovimientoCuentaCorriente.SALDO_INICIAL,
        monto=Decimal("800.00"),
        fecha_origen=timezone.localdate(),
        motivo="Deuda anterior",
    )
    return cajera, admin, efectivo, caja, cliente


def _en_hilo(funcion, resultado):
    def correr():
        try:
            resultado["valor"] = funcion()
        except Exception as error:  # Se revisa en la prueba.
            resultado["error"] = error
        finally:
            resultado["fin"] = time.monotonic()
            connection.close()

    hilo = threading.Thread(target=correr)
    hilo.start()
    return hilo


def test_cp120_un_cobro_durante_el_cierre_espera_y_se_rechaza(escenario):
    cajera, _, efectivo, caja, cliente = escenario
    cerrada = threading.Event()
    cierre, cobro = {}, {}

    def cerrar_y_retener():
        with transaction.atomic():
            cerrar_caja(cajera, {efectivo.pk: Decimal("1000.00")})
            cerrada.set()
            time.sleep(ESPERA)
            cierre["confirmado"] = time.monotonic()

    hilo_cierre = _en_hilo(cerrar_y_retener, cierre)
    assert cerrada.wait(5)
    hilo_cobro = _en_hilo(lambda: registrar_cobro(cajera, cliente, Decimal("300"), efectivo), cobro)
    hilo_cierre.join(10)
    hilo_cobro.join(10)

    assert "error" not in cierre
    assert cobro["fin"] >= cierre["confirmado"]
    assert isinstance(cobro["error"], ValidationError)
    assert cobro["error"].code == "sin_caja"
    assert not PagoCliente.objects.exists()
    assert saldo(cliente) == Decimal("800.00")


def test_cp120_un_cierre_durante_un_cobro_espera_y_lo_incluye(escenario):
    cajera, _, efectivo, caja, cliente = escenario
    cobrado = threading.Event()
    cobro, cierre = {}, {}

    def cobrar_y_retener():
        with transaction.atomic():
            registrar_cobro(cajera, cliente, Decimal("300"), efectivo)
            cobrado.set()
            time.sleep(ESPERA)
            cobro["confirmado"] = time.monotonic()

    hilo_cobro = _en_hilo(cobrar_y_retener, cobro)
    assert cobrado.wait(5)
    # Lo contado coincide con lo esperado solo si el cierre ve el cobro: 1.000 + 300.
    hilo_cierre = _en_hilo(lambda: cerrar_caja(cajera, {efectivo.pk: Decimal("1300.00")}), cierre)
    hilo_cobro.join(10)
    hilo_cierre.join(10)

    assert "error" not in cobro
    assert "error" not in cierre, cierre.get("error")
    assert cierre["fin"] >= cobro["confirmado"]
    assert Caja.objects.get(pk=caja.pk).observacion_cierre == ""
    assert CierreCajaDetalle.objects.get(caja=caja).monto_sistema == Decimal("1300.00")


def test_cp120_una_anulacion_durante_el_cierre_espera_y_se_rechaza(escenario):
    cajera, admin, efectivo, caja, cliente = escenario
    pago = registrar_cobro(cajera, cliente, Decimal("300"), efectivo)
    cerrada = threading.Event()
    cierre, anulacion = {}, {}

    def cerrar_y_retener():
        with transaction.atomic():
            cerrar_caja(cajera, {efectivo.pk: Decimal("1300.00")})
            cerrada.set()
            time.sleep(ESPERA)
            cierre["confirmado"] = time.monotonic()

    hilo_cierre = _en_hilo(cerrar_y_retener, cierre)
    assert cerrada.wait(5)
    hilo_anulacion = _en_hilo(lambda: anular_cobro(admin, pago, "Error"), anulacion)
    hilo_cierre.join(10)
    hilo_anulacion.join(10)

    assert "error" not in cierre
    assert anulacion["fin"] >= cierre["confirmado"]
    # La caja cerrada no recibe la reversa y no hay otra abierta (DEC-166).
    assert anulacion["error"].code == "sin_caja_para_reversa"
    pago.refresh_from_db()
    assert pago.estado == EstadoPagoCliente.VIGENTE
    assert Caja.objects.get(pk=caja.pk).estado == EstadoCaja.CERRADA
    assert MovimientoCaja.objects.filter(caja=caja).count() == 1
