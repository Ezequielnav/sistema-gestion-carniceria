"""Una venta y un cierre de caja a la vez no se cruzan (spec de CU-03, RNF-10, RI-02).

Las dos operaciones bloquean la fila de la caja con select_for_update. Estas pruebas usan
transacciones reales y dos hilos (cada uno con su conexión a la base de prueba).
"""

import threading
import time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.caja.models import Caja, CierreCajaDetalle, EstadoCaja, MedioPago, Turno
from apps.caja.services import abrir_caja, cerrar_caja
from apps.catalogo.models import Producto, UnidadMedida
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import EstadoVenta, Venta
from apps.ventas.services import anular_venta, registrar_venta

pytestmark = pytest.mark.django_db(transaction=True)

ESPERA = 0.5  # segundos que la primera operación retiene el bloqueo antes de confirmar


@pytest.fixture
def escenario():
    cajera = Usuario.objects.create_user(
        username="cajera_concurrencia",
        password="clave-de-prueba-123",
        nombre_completo="Cajera",
        rol=Rol.CAJERA,
    )
    efectivo = MedioPago.objects.create(nombre="Efectivo", es_efectivo=True)
    caja = abrir_caja(cajera, Turno.MANANA, Decimal("5000.00"))
    producto = Producto.objects.create(
        nombre="Carbón 4 kg",
        precio_venta=Decimal("2500.00"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=False,
    )
    return cajera, efectivo, caja, producto


def _en_hilo(funcion, resultado):
    """Corre `funcion` en otro hilo y guarda su resultado o su error y cuándo terminó."""

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


def test_rnf10_una_venta_durante_el_cierre_espera_y_se_rechaza(escenario):
    cajera, efectivo, caja, producto = escenario
    cerrada = threading.Event()
    cierre, venta = {}, {}

    def cerrar_y_retener():
        with transaction.atomic():
            cerrar_caja(cajera, {efectivo.pk: Decimal("5000.00")})
            cerrada.set()
            time.sleep(ESPERA)
            cierre["confirmado"] = time.monotonic()

    hilo_cierre = _en_hilo(cerrar_y_retener, cierre)
    assert cerrada.wait(5)
    hilo_venta = _en_hilo(
        lambda: registrar_venta(cajera, [(producto.pk, Decimal("1"))], efectivo), venta
    )
    hilo_cierre.join(10)
    hilo_venta.join(10)

    assert "error" not in cierre
    # La venta esperó a que el cierre confirmara y entonces ya no encontró la caja abierta.
    assert venta["fin"] >= cierre["confirmado"]
    assert isinstance(venta["error"], ValidationError)
    assert venta["error"].code == "sin_caja"
    assert not Venta.objects.exists()
    caja.refresh_from_db()
    assert caja.estado == EstadoCaja.CERRADA
    assert CierreCajaDetalle.objects.get(caja=caja).monto_sistema == Decimal("5000.00")


def test_rnf10_un_cierre_durante_una_venta_espera_y_la_incluye(escenario):
    cajera, efectivo, caja, producto = escenario
    vendida = threading.Event()
    venta, cierre = {}, {}

    def vender_y_retener():
        with transaction.atomic():
            registrar_venta(cajera, [(producto.pk, Decimal("1"))], efectivo)
            vendida.set()
            time.sleep(ESPERA)
            venta["confirmada"] = time.monotonic()

    hilo_venta = _en_hilo(vender_y_retener, venta)
    assert vendida.wait(5)
    # Lo contado coincide con lo esperado solo si el cierre ve la venta: 5.000 + 2.500.
    hilo_cierre = _en_hilo(lambda: cerrar_caja(cajera, {efectivo.pk: Decimal("7500.00")}), cierre)
    hilo_venta.join(10)
    hilo_cierre.join(10)

    assert "error" not in venta
    assert "error" not in cierre, cierre.get("error")
    assert cierre["fin"] >= venta["confirmada"]
    caja = Caja.objects.get(pk=caja.pk)
    assert caja.estado == EstadoCaja.CERRADA
    assert caja.observacion_cierre == ""
    detalle = CierreCajaDetalle.objects.get(caja=caja)
    assert detalle.monto_sistema == Decimal("7500.00")
    assert Venta.objects.get().caja == caja


def test_rnf10_una_anulacion_durante_el_cierre_espera_y_se_rechaza(escenario):
    cajera, efectivo, caja, producto = escenario
    venta, _ = registrar_venta(cajera, [(producto.pk, Decimal("1"))], efectivo)
    admin = Usuario.objects.create_user(
        username="admin_concurrencia",
        password="clave-de-prueba-123",
        nombre_completo="Administrador",
        rol=Rol.ADMINISTRADOR,
    )
    cerrada = threading.Event()
    cierre, anulacion = {}, {}

    def cerrar_y_retener():
        with transaction.atomic():
            cerrar_caja(cajera, {efectivo.pk: Decimal("7500.00")})
            cerrada.set()
            time.sleep(ESPERA)
            cierre["confirmado"] = time.monotonic()

    hilo_cierre = _en_hilo(cerrar_y_retener, cierre)
    assert cerrada.wait(5)
    hilo_anulacion = _en_hilo(lambda: anular_venta(admin, venta, "Error de carga"), anulacion)
    hilo_cierre.join(10)
    hilo_anulacion.join(10)

    assert "error" not in cierre
    # La anulación esperó al cierre y, con la caja ya cerrada, no tocó nada.
    assert anulacion["fin"] >= cierre["confirmado"]
    assert isinstance(anulacion["error"], ValidationError)
    assert anulacion["error"].code == "caja_cerrada"
    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.CONFIRMADA
    assert CierreCajaDetalle.objects.get(caja=caja).monto_sistema == Decimal("7500.00")
