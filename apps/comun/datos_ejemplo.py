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

# (usuario, nombre completo, rol, puede crear productos, entra al panel)
# "admin" es el superusuario técnico; "admin_negocio" es el Administrador del negocio, sin
# panel, como los que se crean en CU-14 (DEC-150).
USUARIOS = [
    ("admin", "Ana Administradora", Rol.ADMINISTRADOR, False, True),
    ("admin_negocio", "Andrés Administrador", Rol.ADMINISTRADOR, False, False),
    ("cajera_alta", "Carla Cajera", Rol.CAJERA, True, False),
    ("cajera", "Clara Cajera", Rol.CAJERA, False, False),
    ("duenio", "Daniel Dueño", Rol.DUENIO, False, False),
]

# (nombre, ingresa a caja). Cuenta corriente es el único que no ingresa (DEC-41, R-6).
MEDIOS_PAGO = [
    ("Efectivo", True),
    ("Tarjeta", True),
    ("Transferencia", True),
    ("QR", True),
    ("Cuenta corriente", False),
]

CATEGORIAS = ["Vacuno", "Cerdo", "Pollo", "Embutidos", "Almacén", "Bebidas"]

# (nombre, categoría, plus interno, precio, unidad, controla stock, stock actual, stock mínimo).
# La carne se vende por kg y sin control de stock (DEC-36, DEC-79). El stock de los
# demás es un dato ficticio de partida, no una carga de stock inicial (DEC-99).
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

# (nombre, teléfono, dirección, límite de crédito, observaciones). Límite opcional: vacío es
# sin límite y 0, sin crédito habilitado (DEC-108, DEC-115, DEC-117).
CLIENTES = [
    ("Juan Pérez", "381 555-0101", "San Martín 123", "50000.00", "Paga a fin de mes"),
    ("María Gómez", "381 555-0102", "", None, ""),
    ("Comedor Los Álamos", "381 555-0103", "Av. Mate de Luna 456", "150000.00", "Pedido semanal"),
    ("Pedro Ruiz", "381 555-0104", "", "0.00", "Sin crédito hasta regularizar"),
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
    for username, nombre, rol, puede_crear, con_panel in USUARIOS:
        if Usuario.objects.filter(username=username).exists():
            continue
        # Solo el superusuario técnico entra al panel (DEC-32, DEC-150).
        Usuario.objects.create_user(
            username=username,
            password=clave,
            nombre_completo=nombre,
            rol=rol,
            puede_crear_productos=puede_crear,
            is_staff=con_panel,
            is_superuser=con_panel,
        )
        nuevos += 1
    creados["usuarios"] = nuevos

    creados["medios de pago"] = sum(
        _por_nombre(MedioPago, nombre, ingresa_a_caja=ingresa, es_efectivo=nombre == "Efectivo")
        for nombre, ingresa in MEDIOS_PAGO
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
            direccion=direccion,
            limite_credito=_decimal(limite),
            observaciones=observaciones,
        )
        for nombre, telefono, direccion, limite, observaciones in CLIENTES
    )
    creados["proveedores"] = sum(
        _por_nombre(Proveedor, nombre, telefono=telefono, email=email)
        for nombre, telefono, email in PROVEEDORES
    )
    return creados
