"""Datos ficticios para desarrollar y probar en local (H1.3). Nunca datos reales (RNF-16).

La carga es idempotente: cada registro se busca por su clave natural y solo se crea si falta,
así que correrla de nuevo no duplica ni pisa lo que se haya cambiado después.
"""

from decimal import Decimal

from django.db import transaction

from apps.caja.models import MedioPago
from apps.catalogo.models import Categoria, Producto, UnidadMedida
from apps.clientes.models import Cliente
from apps.proveedores.models import Proveedor
from apps.usuarios.models import Rol, Usuario

# (usuario, nombre completo, rol, puede crear productos)
USUARIOS = [
    ("admin", "Ana Administradora", Rol.ADMINISTRADOR, False),
    ("cajera_alta", "Carla Cajera", Rol.CAJERA, True),
    ("cajera", "Clara Cajera", Rol.CAJERA, False),
    ("duenio", "Daniel Dueño", Rol.DUENIO, False),
]

# (nombre, ingresa a caja). Lista a confirmar (PR-08).
MEDIOS_PAGO = [
    ("Efectivo", True),
    ("Tarjeta", True),
    ("Transferencia", True),
    ("QR", True),
    ("Cuenta corriente", False),
]

CATEGORIAS = ["Vacuno", "Cerdo", "Pollo", "Embutidos", "Almacén", "Bebidas"]

# (nombre, categoría, plus interno, precio, unidad, controla stock, stock actual, stock mínimo).
# La carne se vende por kg y sin control de stock (supuesto de PR-01 y PR-03). El stock de los
# demás es un dato ficticio de partida, no una carga de stock inicial (PR-32).
PRODUCTOS = [
    ("Asado", "Vacuno", "101", "9800.00", UnidadMedida.KG, False, "0", None),
    ("Vacío", "Vacuno", "102", "11500.00", UnidadMedida.KG, False, "0", None),
    ("Milanesa de nalga", "Vacuno", "103", "12500.00", UnidadMedida.KG, False, "0", None),
    ("Bondiola", "Cerdo", "201", "8900.00", UnidadMedida.KG, False, "0", None),
    ("Pechuga de pollo", "Pollo", "301", "6500.00", UnidadMedida.KG, False, "0", None),
    ("Chorizo parrillero", "Embutidos", "401", "7200.00", UnidadMedida.KG, False, "0", None),
    ("Aceite de girasol 1,5 l", "Almacén", "501", "3200.00", UnidadMedida.UNIDAD, True, "24", "6"),
    ("Sal fina 500 g", "Almacén", "502", "900.00", UnidadMedida.UNIDAD, True, "3", "5"),
    ("Carbón 4 kg", "Almacén", "503", "5500.00", UnidadMedida.UNIDAD, True, "10", "4"),
    ("Gaseosa cola 2,25 l", "Bebidas", "601", "3500.00", UnidadMedida.UNIDAD, True, "12", "6"),
    ("Agua mineral 2 l", "Bebidas", "602", "1500.00", UnidadMedida.UNIDAD, True, "8", None),
]

# (nombre, teléfono, límite de crédito, condiciones). Límite a confirmar (PR-12).
CLIENTES = [
    ("Juan Pérez", "381 555-0101", "50000.00", "Paga a fin de mes"),
    ("María Gómez", "381 555-0102", None, ""),
    ("Comedor Los Álamos", "381 555-0103", "150000.00", "Pedido semanal"),
]

# (nombre, teléfono, email)
PROVEEDORES = [
    ("Frigorífico del Norte", "381 555-0201", "ventas@frigorifico.example.com"),
    ("Distribuidora La Esquina", "381 555-0202", "pedidos@laesquina.example.com"),
    ("Avícola San Martín", "381 555-0203", ""),
]


def _decimal(valor):
    return Decimal(valor) if valor is not None else None


def _por_nombre(modelo, nombre, **datos):
    """Crea el registro si no hay otro con el mismo nombre, sin distinguir mayúsculas."""
    if modelo.objects.filter(nombre__iexact=nombre).exists():
        return False
    modelo.objects.create(nombre=nombre, **datos)
    return True


@transaction.atomic
def cargar(clave):
    """Carga los datos de ejemplo y devuelve cuántos registros nuevos creó por tipo.

    `clave` es la contraseña de los usuarios nuevos (DEMO_PASSWORD del .env).
    """
    creados = {}

    nuevos = 0
    for username, nombre, rol, puede_crear in USUARIOS:
        if Usuario.objects.filter(username=username).exists():
            continue
        # Solo el Administrador accede al panel de Django (DEC-32).
        es_admin = rol == Rol.ADMINISTRADOR
        Usuario.objects.create_user(
            username=username,
            password=clave,
            nombre_completo=nombre,
            rol=rol,
            puede_crear_productos=puede_crear,
            is_staff=es_admin,
            is_superuser=es_admin,
        )
        nuevos += 1
    creados["usuarios"] = nuevos

    creados["medios de pago"] = sum(
        _por_nombre(MedioPago, nombre, ingresa_a_caja=ingresa) for nombre, ingresa in MEDIOS_PAGO
    )
    creados["categorías"] = sum(_por_nombre(Categoria, nombre) for nombre in CATEGORIAS)

    nuevos = 0
    for nombre, categoria, plus, precio, unidad, controla, stock, minimo in PRODUCTOS:
        if Producto.objects.filter(plus_interno=plus).exists():
            continue
        Producto.objects.create(
            nombre=nombre,
            categoria=Categoria.objects.get(nombre__iexact=categoria),
            plus_interno=plus,
            precio_venta=Decimal(precio),
            unidad_medida=unidad,
            controla_stock=controla,
            stock_actual=Decimal(stock),
            stock_minimo=_decimal(minimo),
        )
        nuevos += 1
    creados["productos"] = nuevos

    creados["clientes"] = sum(
        _por_nombre(
            Cliente,
            nombre,
            telefono=telefono,
            limite_credito=_decimal(limite),
            condiciones=condiciones,
        )
        for nombre, telefono, limite, condiciones in CLIENTES
    )
    creados["proveedores"] = sum(
        _por_nombre(Proveedor, nombre, telefono=telefono, email=email)
        for nombre, telefono, email in PROVEEDORES
    )
    return creados
