"""Datos ficticios mínimos compartidos por las pruebas (RNF-16)."""

import datetime
import os
from decimal import Decimal

import pytest
from django.conf import settings
from django.test import Client

from apps.caja.models import Caja, MedioPago, Turno
from apps.catalogo.models import Categoria, Producto, UnidadMedida
from apps.clientes.models import Cliente, PagoCliente
from apps.proveedores.models import CondicionPago, IngresoMercaderia, PagoProveedor, Proveedor
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import Venta

FECHA = datetime.date(2026, 1, 15)


@pytest.fixture
def usuario(db):
    return Usuario.objects.create_user(
        username="cajera1",
        password="clave-de-prueba-123",
        nombre_completo="Cajera Uno",
        rol=Rol.CAJERA,
    )


@pytest.fixture
def efectivo(db):
    return MedioPago.objects.create(nombre="Efectivo", es_efectivo=True)


@pytest.fixture
def caja(usuario):
    return Caja.objects.create(fecha=FECHA, turno=Turno.MANANA, usuario=usuario)


@pytest.fixture
def categoria(db):
    return Categoria.objects.create(nombre="Almacén")


@pytest.fixture
def producto(categoria):
    return Producto.objects.create(
        nombre="Aceite 1 l",
        categoria=categoria,
        precio_venta=Decimal("2500.00"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=True,
    )


@pytest.fixture
def cliente(db):
    return Cliente.objects.create(nombre="Cliente de prueba")


@pytest.fixture
def proveedor(db):
    return Proveedor.objects.create(nombre="Proveedor de prueba")


@pytest.fixture
def venta(caja, usuario, efectivo):
    return Venta.objects.create(
        caja=caja, usuario=usuario, medio_pago=efectivo, monto_total=Decimal("2500.00")
    )


@pytest.fixture
def pago_cliente(cliente, efectivo, usuario):
    return PagoCliente.objects.create(
        cliente=cliente, monto=Decimal("1000.00"), medio_pago=efectivo, usuario=usuario
    )


@pytest.fixture
def ingreso(proveedor, usuario):
    return IngresoMercaderia.objects.create(
        fecha=FECHA,
        proveedor=proveedor,
        usuario=usuario,
        total=Decimal("5000.00"),
        condicion_pago=CondicionPago.CONTADO,
    )


@pytest.fixture
def pago_proveedor(proveedor, efectivo, usuario):
    return PagoProveedor.objects.create(
        proveedor=proveedor, monto=Decimal("1000.00"), medio_pago=efectivo, usuario=usuario
    )


# Pruebas de navegador (L2, DEC-160, DEC-180). Se marcan `navegador` para correrlas aparte
# (`pytest -m navegador`) o excluirlas (`pytest -m "not navegador"`). Usan Chromium con
# Playwright, el servidor de pruebas de Django y la base de prueba; los usuarios los crea cada
# prueba, sin `.env` ni datos de ejemplo. Sin Playwright o sin Chromium instalado, se saltean.

_CHROMIUM = {}


def _chromium_disponible():
    if "ok" not in _CHROMIUM:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                p.chromium.launch().close()
            _CHROMIUM["ok"] = True
        except Exception:  # sin el paquete o sin el navegador descargado
            _CHROMIUM["ok"] = False
    return _CHROMIUM["ok"]


def pytest_collection_modifyitems(config, items):
    de_navegador = [item for item in items if item.get_closest_marker("navegador")]
    if not de_navegador:
        return
    if not _chromium_disponible():
        saltear = pytest.mark.skip(
            reason="Falta Chromium para Playwright: correr `.venv/bin/playwright install chromium`"
        )
        for item in de_navegador:
            item.add_marker(saltear)
        return
    # Al final: una vez que arranca, Playwright deja su bucle de eventos en el hilo de las
    # pruebas hasta terminar la corrida, y ninguna prueba sin navegador debe correr con él.
    items[:] = [item for item in items if item not in de_navegador] + de_navegador


_ASINCRONO = "DJANGO_ALLOW_ASYNC_UNSAFE"


def pytest_runtest_setup(item):
    """Permite el contexto asíncrono solo en las pruebas `navegador` (antes de sus fixtures, que
    pueden crear la base de prueba con el bucle de Playwright ya corriendo). Django lo exige
    porque el API síncrono de Playwright deja un bucle de eventos en el hilo; la aplicación no
    tiene código asíncrono. En cualquier otra prueba se quita, así un desorden falla a la vista."""
    if item.get_closest_marker("navegador"):
        os.environ[_ASINCRONO] = "true"
    else:
        os.environ.pop(_ASINCRONO, None)


def pytest_sessionfinish(session):
    os.environ.pop(_ASINCRONO, None)


@pytest.fixture
def navegador(page, live_server):
    """La página de Playwright apuntando al servidor de pruebas, con `entrar(usuario)` para
    iniciar sesión sin escribir la contraseña (la sesión se crea con el cliente de Django)."""
    page.set_default_timeout(10_000)

    def entrar(usuario):
        cliente = Client()
        cliente.force_login(usuario)
        page.context.add_cookies(
            [
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": cliente.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": live_server.url,
                }
            ]
        )
        return page

    page.entrar = entrar
    page.url_de = lambda ruta: f"{live_server.url}{ruta}"
    return page
