"""Datos ficticios mínimos compartidos por las pruebas (RNF-16)."""

import datetime
from decimal import Decimal

import pytest

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
    return MedioPago.objects.create(nombre="Efectivo")


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
