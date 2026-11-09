"""Menú de funciones por rol (RF-02, H1.4).

Solo incluye lo confirmado (C) en la matriz de actores de 04 (sección 2). Los casos
marcados "a confirmar" (los dueños, PR-25) se agregan cuando el negocio los confirme.
"""

from dataclasses import dataclass

from apps.usuarios.models import Rol


@dataclass(frozen=True)
class Funcion:
    nombre: str
    descripcion: str
    casos_de_uso: str
    roles: frozenset
    # Nombre del ícono en templates/comun/_icono.html: uno distinto por función, el mismo en el
    # menú y en los accesos del inicio (H7).
    icono: str = ""
    # Nombre de la URL; vacío mientras el caso de uso no está construido.
    url: str = ""


ADMIN = Rol.ADMINISTRADOR
CAJERA = Rol.CAJERA
DUENIO = Rol.DUENIO

FUNCIONES = [
    Funcion(
        "Ventas",
        "Cobrar en el mostrador",
        "CU-01",
        frozenset({CAJERA}),
        "carrito",
        url="ventas:nueva",
    ),
    Funcion(
        "Ventas de la caja",
        "Revisar las ventas de la caja abierta",
        "CU-01 (DEC-84)",
        frozenset({CAJERA}),
        "recibo",
        url="ventas:lista",
    ),
    Funcion(
        "Historial de ventas",
        "Buscar ventas y anular las de la caja abierta",
        "CU-01 (DEC-45, DEC-86)",
        frozenset({ADMIN}),
        "historial",
        url="ventas:historial",
    ),
    Funcion(
        "Caja",
        "Abrir y cerrar el turno",
        "CU-02, CU-03",
        frozenset({CAJERA}),
        "billete",
        url="caja:caja",
    ),
    # S-2 (DEC-121): la cajera cobra cuentas corrientes, sin gestionar clientes (DEC-110, DEC-116).
    Funcion(
        "Cobrar cuenta corriente",
        "Cobrar a clientes en la caja",
        "CU-04 (DEC-110)",
        frozenset({CAJERA}),
        "cobro",
        url="clientes:cobrar",
    ),
    # DEC-103: toda cajera consulta productos y stock; el alta sigue con permiso (RN-05).
    # DEC-105: la consulta de stock (CU-06) vive acá, sin función propia en el menú.
    Funcion(
        "Productos",
        "Precios, stock y altas",
        "CU-06, CU-11",
        frozenset({ADMIN, CAJERA}),
        "paquete",
        url="catalogo:productos",
    ),
    Funcion(
        "Clientes",
        "Cuentas corrientes y cobros",
        "CU-04, CU-08, CU-12",
        frozenset({ADMIN}),
        "personas",
        url="clientes:clientes",  # S-2 (DEC-121); estado de cuenta y cobro en las etapas 4 y 5
    ),
    Funcion(
        "Proveedores",
        "Proveedores, ingresos y pagos",
        "CU-05, CU-07, CU-13",
        frozenset({ADMIN}),
        "camion",
        url="proveedores:proveedores",  # DEC-88; ingresos y pagos en las etapas 3 y 4
    ),
    Funcion(
        "Reportes",
        "Ventas, ingresos y cierres",
        "CU-09",
        frozenset({ADMIN, DUENIO}),
        "grafico",
        url="reportes:inicio",  # DEC-136; los dueños, solo esto (DEC-134)
    ),
    # DEC-155 (L18): sin entrar al panel, el Administrador mantiene los medios de pago.
    Funcion(
        "Medios de pago",
        "Efectivo, tarjetas y otros medios",
        "DEC-155",
        frozenset({ADMIN}),
        "tarjeta",
        url="caja:medios",
    ),
    Funcion(
        "Usuarios",
        "Cuentas y roles",
        "CU-14",
        frozenset({ADMIN}),
        "usuario",
        url="usuarios:usuarios",  # DEC-149
    ),
]


def puede_usar(usuario, funcion):
    """Si el rol del usuario tiene la función (RF-02)."""
    return usuario.is_authenticated and usuario.rol in funcion.roles


def funciones_para(usuario):
    """Funciones que el usuario ve en el menú según su rol."""
    return [funcion for funcion in FUNCIONES if puede_usar(usuario, funcion)]
