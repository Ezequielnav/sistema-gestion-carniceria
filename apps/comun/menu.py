"""Menú de funciones por rol (RF-02, H1.4).

Solo incluye lo confirmado (C) en la matriz de actores de 04 (sección 2). Los casos
marcados "a confirmar" (PR-14, PR-25) se agregan cuando el negocio los confirme.
"""

from dataclasses import dataclass

from apps.usuarios.models import Rol


@dataclass(frozen=True)
class Funcion:
    nombre: str
    descripcion: str
    casos_de_uso: str
    roles: frozenset
    # Nombre del ícono en templates/comun/_icono.html.
    icono: str = ""
    # Nombre de la URL; vacío mientras el caso de uso no está construido.
    url: str = ""
    # Solo para la cajera con permiso de alta de productos (RN-05).
    requiere_alta_productos: bool = False


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
        "Caja",
        "Abrir y cerrar el turno",
        "CU-02, CU-03",
        frozenset({CAJERA}),
        "billetera",
        url="caja:caja",
    ),
    Funcion(
        "Productos",
        "Precios, categorías y altas",
        "CU-11",
        frozenset({ADMIN, CAJERA}),
        "paquete",
        url="catalogo:productos",
        requiere_alta_productos=True,
    ),
    Funcion("Stock", "Existencias y faltantes", "CU-06", frozenset({ADMIN}), "capas"),
    Funcion(
        "Clientes",
        "Cuentas corrientes y cobros",
        "CU-04, CU-08, CU-12",
        frozenset({ADMIN}),
        "personas",
    ),
    Funcion(
        "Proveedores",
        "Ingresos de mercadería y pagos",
        "CU-05, CU-07, CU-13",
        frozenset({ADMIN}),
        "camion",
    ),
    Funcion("Reportes", "Ventas, caja y saldos", "CU-09", frozenset({ADMIN, DUENIO}), "grafico"),
    Funcion("Usuarios", "Cuentas y roles", "CU-14", frozenset({ADMIN}), "usuario"),
]


def puede_usar(usuario, funcion):
    """Si el rol del usuario tiene la función (RF-02; RN-05 para la cajera)."""
    if not usuario.is_authenticated or usuario.rol not in funcion.roles:
        return False
    if funcion.requiere_alta_productos and usuario.rol == CAJERA:
        return usuario.puede_crear_productos
    return True


def funciones_para(usuario):
    """Funciones que el usuario ve en el menú según su rol."""
    return [funcion for funcion in FUNCIONES if puede_usar(usuario, funcion)]
