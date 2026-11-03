"""Dos ventas a cuenta corriente del mismo cliente a la vez no pasan juntas el límite (S-9,
DEC-128, DEC-108).

Las ventas bloquean la caja, después el cliente y después los productos. Estas pruebas usan
transacciones reales y dos hilos, como CP-88.
"""

import threading
import time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.caja.models import MedioPago, Turno
from apps.caja.services import abrir_caja
from apps.catalogo.models import Producto, UnidadMedida
from apps.clientes.models import Cliente, MovimientoCuentaCorriente
from apps.clientes.services import saldo
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import Venta
from apps.ventas.services import registrar_venta

pytestmark = pytest.mark.django_db(transaction=True)

ESPERA = 0.5  # segundos que la primera venta retiene los bloqueos antes de confirmar


@pytest.fixture
def escenario():
    cajera = Usuario.objects.create_user(
        username="cajera_cuenta_corriente",
        password="clave-de-prueba-123",
        nombre_completo="Cajera",
        rol=Rol.CAJERA,
    )
    MedioPago.objects.create(nombre="Efectivo", es_efectivo=True)
    cuenta_corriente = MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)
    abrir_caja(cajera, Turno.MANANA)
    producto = Producto.objects.create(
        nombre="Carbón 4 kg",
        precio_venta=Decimal("600.00"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=False,
    )
    cliente = Cliente.objects.create(nombre="Juan Pérez", limite_credito=Decimal("1000.00"))
    return cajera, cuenta_corriente, producto, cliente


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


def test_s9_la_segunda_venta_espera_y_se_rechaza_por_el_limite(escenario):
    cajera, cuenta_corriente, producto, cliente = escenario
    vendida = threading.Event()
    primera, segunda = {}, {}

    def vender_y_retener():
        with transaction.atomic():
            registrar_venta(cajera, [(producto.pk, Decimal("1"))], cuenta_corriente, cliente)
            vendida.set()
            time.sleep(ESPERA)
            primera["confirmada"] = time.monotonic()

    hilo_primera = _en_hilo(vender_y_retener, primera)
    assert vendida.wait(5)
    hilo_segunda = _en_hilo(
        lambda: registrar_venta(cajera, [(producto.pk, Decimal("1"))], cuenta_corriente, cliente),
        segunda,
    )
    hilo_primera.join(10)
    hilo_segunda.join(10)

    assert "error" not in primera
    # La segunda esperó a la primera y vio su deuda: 600 + 600 pasa el límite de 1.000.
    assert segunda["fin"] >= primera["confirmada"]
    assert isinstance(segunda["error"], ValidationError)
    assert segunda["error"].code == "limite_superado"
    assert Venta.objects.count() == 1
    assert MovimientoCuentaCorriente.objects.count() == 1
    assert saldo(cliente) == Decimal("600.00")
