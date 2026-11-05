from django import forms
from django.utils import timezone


class RangoFechasForm(forms.Form):
    """Rango de fechas de los listados y reportes (DEC-145): "desde" no puede ser posterior a
    "hasta" ni "hasta" posterior a hoy (CU-09 A2).

    Lo usan los reportes de CU-09 (con el rango obligatorio), la consulta de ajustes de stock y
    los listados de ingresos y pagos a proveedores (opcional, DEC-152).
    """

    obligatorio = False

    desde = forms.DateField(label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = timezone.localdate().isoformat()
        for nombre in ("desde", "hasta"):
            self.fields[nombre].required = self.obligatorio
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"
            if isinstance(campo, forms.DateField):
                campo.widget.attrs["max"] = hoy

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if hasta and hasta > timezone.localdate():
            self.add_error("hasta", "La fecha no puede ser posterior a hoy.")
        if desde and hasta and desde > hasta:
            self.add_error("desde", "«Desde» no puede ser posterior a «hasta». Corregí el rango.")
        return datos
