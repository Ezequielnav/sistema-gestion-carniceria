"""Permisos por rol de las pantallas (RF-02, RNF-06).

Usa la misma tabla de funciones que el menú (apps/comun/menu.py): una pantalla se puede
abrir solo si su función aparece en el menú del usuario.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from apps.comun.menu import FUNCIONES, puede_usar


def requiere_funcion(nombre):
    """Vista solo para usuarios con sesión cuyo rol tiene la función `nombre` (403 si no)."""
    funcion = next(f for f in FUNCIONES if f.nombre == nombre)

    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            if not puede_usar(request.user, funcion):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
