import json
from decimal import Decimal, InvalidOperation

from django import forms

from apps.caja.models import MedioPago
from apps.ventas.services import medios_de_pago_para_venta


class ConfirmarVentaForm(forms.Form):
    """Medio de pago y lista de la venta (DEC-47). Las reglas las aplica el servicio."""

    medio_pago = forms.ModelChoiceField(
        queryset=MedioPago.objects.none(),
        label="Medio de pago",
        empty_label="Elegí un medio de pago",
        error_messages={
            "required": "Elegí un medio de pago.",
            "invalid_choice": "Ese medio de pago no se puede usar en la venta.",
        },
    )
    # Lista en JSON: [{"producto": id, "cantidad": "1.250"}]. Los precios no viajan.
    lineas = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sin valor por defecto (DEC-51) y sin cuenta corriente hasta H4 (DEC-41).
        self.fields["medio_pago"].queryset = medios_de_pago_para_venta()
        self.fields["medio_pago"].widget.attrs["class"] = "campo"

    def clean_lineas(self):
        try:
            datos = json.loads(self.cleaned_data["lineas"] or "[]")
            lineas = [(int(d["producto"]), Decimal(str(d["cantidad"]))) for d in datos]
        except (ValueError, TypeError, KeyError, InvalidOperation) as error:
            raise forms.ValidationError("La lista de productos no es válida.") from error
        if not all(cantidad.is_finite() for _, cantidad in lineas):
            raise forms.ValidationError("La lista de productos no es válida.")
        return lineas
