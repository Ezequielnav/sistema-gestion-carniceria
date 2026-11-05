from decimal import Decimal

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
        # Solo los turnos que se pueden abrir (DEC-83); el servicio lo valida igual.
        self.fields["turno"].choices = [("", "Elegí un turno")] + [
            (turno.value, turno.label) for turno in turnos
        ]
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"
        # Mínimo del navegador; la regla la valida el servicio (RI-16).
        self.fields["monto_inicial"].widget.attrs["min"] = "0"


class EgresoForm(forms.Form):
    """Egreso "otro" en efectivo (DEC-43). Las reglas (DEC-57, RI-13) las aplica el servicio."""

    monto = forms.DecimalField(label="Monto", max_digits=12, decimal_places=2)
    descripcion = forms.CharField(
        label="Descripción",
        max_length=255,
        help_text="Por ejemplo: bolsas, limpieza o retiro para el dueño.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"
        self.fields["monto"].widget.attrs["min"] = "0.01"


class CierreForm(forms.Form):
    """Lo contado por medio de pago y el motivo. Las reglas (RI-10, DEC-40) van en el servicio."""

    observacion = forms.CharField(
        label="Motivo de la diferencia",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obligatorio si lo contado no coincide con lo esperado.",
    )

    def __init__(self, *args, resumen, **kwargs):
        super().__init__(*args, **kwargs)
        self.resumen = resumen
        campos = {}
        for medio, _ in resumen:
            campos[f"contado_{medio.pk}"] = forms.DecimalField(
                label=f"Contado en {medio}",
                max_digits=12,
                decimal_places=2,
                min_value=Decimal("0"),
                error_messages={
                    "required": f"Falta lo contado en {medio}.",
                    "min_value": "No puede ser negativo.",
                },
            )
        self.fields = {**campos, **self.fields}
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"
        for nombre in campos:
            self.fields[nombre].widget.attrs["min"] = "0"

    def filas(self):
        """Por medio: (medio, esperado, campo de contado) para la plantilla."""
        return [(medio, esperado, self[f"contado_{medio.pk}"]) for medio, esperado in self.resumen]

    def contados(self):
        return {medio.pk: self.cleaned_data[f"contado_{medio.pk}"] for medio, _ in self.resumen}


class MedioPagoForm(forms.Form):
    """Medio de pago (DEC-155). En la edición solo el nombre; las reglas, en el servicio."""

    nombre = forms.CharField(label="Nombre", max_length=50)
    ingresa_a_caja = forms.BooleanField(
        label="Ingresa a caja",
        required=False,
        initial=True,
        help_text=(
            "Desmarcado solo para la cuenta corriente: la venta queda como deuda del cliente "
            "(DEC-41)."
        ),
    )
    es_efectivo = forms.BooleanField(
        label="Es efectivo",
        required=False,
        help_text="Uno solo: el del fondo de cambio y los egresos (DEC-55).",
    )

    def __init__(self, *args, es_alta=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not es_alta:
            del self.fields["ingresa_a_caja"]
            del self.fields["es_efectivo"]
        for campo in self.fields.values():
            clase = "casilla" if isinstance(campo.widget, forms.CheckboxInput) else "campo"
            campo.widget.attrs["class"] = clase
