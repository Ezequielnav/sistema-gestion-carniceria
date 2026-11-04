from django.utils import timezone

from apps.comun.forms import RangoFechasForm


class RangoForm(RangoFechasForm):
    """Rango del reporte (DEC-145): obligatorio y, si no viene, el día de hoy."""

    obligatorio = True

    def __init__(self, datos, *args, **kwargs):
        # Sin rango en la dirección, el de hoy; con uno, se valida tal cual vino.
        if not datos.get("desde") and not datos.get("hasta"):
            hoy = timezone.localdate().isoformat()
            datos = {"desde": hoy, "hasta": hoy}
        super().__init__(datos, *args, **kwargs)
