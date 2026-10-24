from apps.catalogo.models import Producto


def cantidad_de_productos_activos():
    return Producto.objects.filter(activo=True).count()
