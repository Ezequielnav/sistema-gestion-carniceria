from django import forms


class AbrirCajaForm(forms.Form):
    """Datos de la apertura. Las reglas (RN-01, DEC-38, DEC-39, RI-16) las aplica el servicio."""

    turno = forms.ChoiceField(label="Turno")
    monto_inicial = forms.DecimalField(
        label="Fondo de cambio",
        required=False,
        max_digits=12,
        decimal_places=2,
        help_text="Opcional. Efectivo para dar cambio; si lo dejás vacío, se guarda 0.",
    )

    def __init__(self, *args, turnos, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo los turnos que se pueden abrir hoy (DEC-39); el servicio lo valida igual.
        self.fields["turno"].choices = [("", "Elegí un turno")] + [
            (turno.value, turno.label) for turno in turnos
        ]
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"
        # Mínimo del navegador; la regla la valida el servicio (RI-16).
        self.fields["monto_inicial"].widget.attrs["min"] = "0"
