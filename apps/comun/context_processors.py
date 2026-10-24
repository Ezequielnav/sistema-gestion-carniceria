from apps.comun.menu import funciones_para


def menu(request):
    """Pone en toda plantilla las funciones del menú del usuario (RF-02)."""
    return {"menu": funciones_para(request.user)}
