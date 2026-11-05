import datetime

from django.utils import timezone

from apps.comun.forms import RangoFechasForm


class RangoForm(RangoFechasForm):
    """Rango del reporte (DEC-145): obligatorio y, si no viene, los últimos `dias` días hasta
    hoy: el día de hoy en cada reporte y 30 días en el Resumen (DEC-158)."""

    obligatorio = True

    def __init__(self, datos, *args, dias=1, **kwargs):
        # Sin rango en la dirección, el de por defecto; con uno, se valida tal cual vino.
        if not datos.get("desde") and not datos.get("hasta"):
            hoy = timezone.localdate()
            desde = hoy - datetime.timedelta(days=dias - 1)
            datos = {"desde": desde.isoformat(), "hasta": hoy.isoformat()}
        super().__init__(datos, *args, **kwargs)
