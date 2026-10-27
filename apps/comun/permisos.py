"""Permisos por rol de las pantallas (RF-02, RNF-06).

Usa la misma tabla de funciones que el menú (apps/comun/menu.py): una pantalla se puede
abrir solo si su función aparece en el menú del usuario.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from apps.comun.menu import FUNCIONES, puede_usar


def requiere_funcion(*nombres):
    """Vista solo para usuarios con sesión cuyo rol tiene alguna de las funciones (403 si no)."""
    funciones = []
    for nombre in nombres:
        funcion = next((f for f in FUNCIONES if f.nombre == nombre), None)
        if funcion is None:
            raise ValueError(
                f"requiere_funcion: no existe la función {nombre!r} en apps/comun/menu.py"
            )
        funciones.append(funcion)

    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            if not any(puede_usar(request.user, funcion) for funcion in funciones):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
