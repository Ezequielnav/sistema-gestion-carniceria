from apps.caja.models import Caja, EstadoCaja


def cajas_abiertas():
    return list(Caja.objects.filter(estado=EstadoCaja.ABIERTA).order_by("fecha", "turno"))
