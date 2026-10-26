"""H1.3: comando de datos de ejemplo."""

from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command

from apps.caja.models import MedioPago
from apps.catalogo.models import Categoria, Producto
from apps.clientes.models import Cliente
from apps.comun.datos_ejemplo import USUARIOS
from apps.proveedores.models import Proveedor
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

CLAVE = "clave-de-prueba-123"
MODELOS = [Usuario, MedioPago, Categoria, Producto, Cliente, Proveedor]


@pytest.fixture
def desarrollo(settings):
    settings.DEBUG = True
    settings.DEMO_PASSWORD = CLAVE


def _cargar():
    call_command("cargar_datos_ejemplo", stdout=StringIO())


def _cantidades():
    return {m.__name__: m.objects.count() for m in MODELOS}


def test_carga_un_usuario_por_rol_y_las_dos_cajeras(desarrollo):
    _cargar()

    assert set(Usuario.objects.values_list("rol", flat=True)) == set(Rol.values)
    cajeras = Usuario.objects.filter(rol=Rol.CAJERA)
    assert sorted(cajeras.values_list("puede_crear_productos", flat=True)) == [False, True]
    assert list(Usuario.objects.filter(is_staff=True).values_list("rol", flat=True)) == [
        Rol.ADMINISTRADOR
    ]


def test_carga_medios_de_pago_y_cuenta_corriente_no_ingresa_a_caja(desarrollo):
    _cargar()

    assert set(MedioPago.objects.values_list("nombre", flat=True)) == {
        "Efectivo",
        "Tarjeta",
        "Transferencia",
        "QR",
        "Cuenta corriente",
    }
    assert list(
        MedioPago.objects.filter(ingresa_a_caja=False).values_list("nombre", flat=True)
    ) == ["Cuenta corriente"]
    assert list(MedioPago.objects.filter(es_efectivo=True).values_list("nombre", flat=True)) == [
        "Efectivo"
    ]


def test_carga_productos_con_y_sin_control_de_stock(desarrollo):
    _cargar()

    assert Producto.objects.filter(controla_stock=False).exists()
    assert Producto.objects.filter(controla_stock=True, stock_minimo__isnull=False).exists()
    assert Categoria.objects.exists() and Cliente.objects.exists() and Proveedor.objects.exists()


def test_correrlo_dos_veces_no_duplica(desarrollo):
    _cargar()
    antes = _cantidades()

    _cargar()

    assert _cantidades() == antes


def test_cada_usuario_de_ejemplo_entra_con_la_clave(desarrollo):
    _cargar()

    for username, *_ in USUARIOS:
        assert authenticate(username=username, password=CLAVE) is not None, username


def test_no_corre_fuera_de_desarrollo(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="desarrollo"):
        _cargar()

    assert not Usuario.objects.exists()


def test_sin_demo_password_no_carga_nada(desarrollo, settings):
    settings.DEMO_PASSWORD = ""

    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        _cargar()

    assert not any(_cantidades().values())
