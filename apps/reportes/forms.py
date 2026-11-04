from django import forms
from django.utils import timezone


class RangoForm(forms.Form):
    """Rango del reporte (DEC-145): obligatorio, por defecto hoy; desde no puede ser posterior
    a hasta (CU-09 A2) ni hasta posterior a hoy."""

    desde = forms.DateField(label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, datos, *args, **kwargs):
        hoy = timezone.localdate().isoformat()
        # Sin rango en la dirección, el de hoy; con uno, se valida tal cual vino.
        if not datos.get("desde") and not datos.get("hasta"):
            datos = {"desde": hoy, "hasta": hoy}
        super().__init__(datos, *args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "campo", "max": hoy})

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if hasta and hasta > timezone.localdate():
            self.add_error("hasta", "La fecha no puede ser posterior a hoy.")
        if desde and hasta and desde > hasta:
            self.add_error("desde", "«Desde» no puede ser posterior a «hasta». Corregí el rango.")
        return datos
