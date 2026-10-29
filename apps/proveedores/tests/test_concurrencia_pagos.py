"""Un pago a proveedor no se cruza con el cierre de caja ni con la anulación del ingreso.

El pago bloquea el ingreso (como la anulación) y, en efectivo, la caja (como el cierre).
Transacciones reales y dos hilos, como CP-88.
"""

import threading
import time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.caja.models import CierreCajaDetalle, EstadoCaja, MedioPago, MovimientoCaja, Turno
from apps.caja.services import abrir_caja, cerrar_caja
from apps.catalogo.models import Producto, UnidadMedida
from apps.proveedores.models import EstadoIngreso, PagoProveedor, Proveedor
from apps.proveedores.services import anular_ingreso, registrar_ingreso, registrar_pago
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db(transaction=True)

ESPERA = 0.5


@pytest.fixture
def escenario():
    def crear(username, rol):
        return Usuario.objects.create_user(
            username=username, password="clave-de-prueba-123", nombre_completo=username, rol=rol
        )

    cajera = crear("cajera_pagos", Rol.CAJERA)
    admin = crear("admin_pagos", Rol.ADMINISTRADOR)
    efectivo = MedioPago.objects.create(nombre="Efectivo", es_efectivo=True)
    # No ingresa a caja: el cierre no pide contarla.
    MedioPago.objects.create(nombre="Transferencia", es_transferencia=True, ingresa_a_caja=False)
    caja = abrir_caja(cajera, Turno.MANANA, Decimal("5000.00"))
    producto = Producto.objects.create(
        nombre="Carbón 4 kg",
        precio_venta=Decimal("2500.00"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=False,
    )
    proveedor = Proveedor.objects.create(nombre="Proveedor de prueba")
    ingreso = registrar_ingreso(admin, proveedor, [(producto.pk, Decimal("1"), Decimal("1000"))])
    return cajera, admin, efectivo, caja, ingreso


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


def test_un_pago_en_efectivo_durante_el_cierre_espera_y_se_rechaza(escenario):
    cajera, admin, efectivo, caja, ingreso = escenario
    cerrada = threading.Event()
    cierre, pago = {}, {}

    def cerrar_y_retener():
        with transaction.atomic():
            cerrar_caja(cajera, {efectivo.pk: Decimal("5000.00")})
            cerrada.set()
            time.sleep(ESPERA)
            cierre["confirmado"] = time.monotonic()

    hilo_cierre = _en_hilo(cerrar_y_retener, cierre)
    assert cerrada.wait(5)
    hilo_pago = _en_hilo(lambda: registrar_pago(admin, ingreso, Decimal("300"), efectivo), pago)
    hilo_cierre.join(10)
    hilo_pago.join(10)

    assert "error" not in cierre
    assert pago["fin"] >= cierre["confirmado"]
    assert isinstance(pago["error"], ValidationError) and pago["error"].code == "sin_caja"
    assert not PagoProveedor.objects.exists() and not MovimientoCaja.objects.exists()


def test_un_cierre_durante_un_pago_en_efectivo_espera_y_lo_incluye(escenario):
    cajera, admin, efectivo, caja, ingreso = escenario
    pagado = threading.Event()
    pago, cierre = {}, {}

    def pagar_y_retener():
        with transaction.atomic():
            registrar_pago(admin, ingreso, Decimal("300"), efectivo)
            pagado.set()
            time.sleep(ESPERA)
            pago["confirmado"] = time.monotonic()

    hilo_pago = _en_hilo(pagar_y_retener, pago)
    assert pagado.wait(5)
    hilo_cierre = _en_hilo(lambda: cerrar_caja(cajera, {efectivo.pk: Decimal("4700.00")}), cierre)
    hilo_pago.join(10)
    hilo_cierre.join(10)

    assert "error" not in pago and "error" not in cierre
    assert cierre["fin"] >= pago["confirmado"]
    caja.refresh_from_db()
    assert caja.estado == EstadoCaja.CERRADA
    assert CierreCajaDetalle.objects.get(caja=caja).monto_sistema == Decimal("4700.00")


def test_un_pago_durante_la_anulacion_del_ingreso_espera_y_se_rechaza(escenario):
    cajera, admin, efectivo, caja, ingreso = escenario
    transferencia = MedioPago.objects.get(es_transferencia=True)
    anulado = threading.Event()
    anulacion, pago = {}, {}

    def anular_y_retener():
        with transaction.atomic():
            anular_ingreso(admin, ingreso, "Error de carga")
            anulado.set()
            time.sleep(ESPERA)
            anulacion["confirmado"] = time.monotonic()

    hilo_anulacion = _en_hilo(anular_y_retener, anulacion)
    assert anulado.wait(5)
    hilo_pago = _en_hilo(
        lambda: registrar_pago(admin, ingreso, Decimal("300"), transferencia), pago
    )
    hilo_anulacion.join(10)
    hilo_pago.join(10)

    assert "error" not in anulacion
    assert pago["fin"] >= anulacion["confirmado"]
    assert "anulado" in pago["error"].messages[0]
    ingreso.refresh_from_db()
    assert ingreso.estado == EstadoIngreso.ANULADO and not PagoProveedor.objects.exists()
