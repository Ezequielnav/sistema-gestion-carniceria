from django.conf import settings
from django.urls import reverse

from apps.comun.menu import funciones_para

# S-4 (DEC-190): el archivo original del logo provisorio va en esta carpeta de static.
CARPETA_LOGO = "img/logo"
EXTENSIONES_LOGO = (".svg", ".png", ".webp")


def menu(request):
    """Pone en toda plantilla las funciones del menú del usuario (RF-02) y cuál es la
    actual (S-5, DEC-191): la de la URL más larga que contiene a la ruta pedida, para que
    las pantallas internas (editar, detalle) también marquen su función."""
    funciones = funciones_para(request.user)
    actual = None
    largo = 0
    for funcion in funciones:
        if not funcion.url:
            continue
        ruta = reverse(funcion.url)
        if request.path.startswith(ruta) and len(ruta) > largo:
            actual, largo = funcion.url, len(ruta)
    return {"menu": funciones, "menu_actual": actual}


def marca(request):
    """El logo, si su archivo ya está en `static/img/logo/` (S-4); si no, las plantillas
    muestran la marca tipográfica."""
    return {"logo": logo()}


def logo():
    for carpeta in settings.STATICFILES_DIRS:
        directorio = carpeta / CARPETA_LOGO
        if not directorio.is_dir():
            continue
        for archivo in sorted(directorio.iterdir()):
            if archivo.suffix.lower() in EXTENSIONES_LOGO:
                return f"{CARPETA_LOGO}/{archivo.name}"
    return None
