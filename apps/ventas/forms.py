import json
from decimal import Decimal, InvalidOperation

from django import forms

from apps.caja.models import MedioPago, Turno
from apps.clientes.models import Cliente
from apps.ventas.services import cajas_para_filtrar, medios_de_pago_para_venta


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
    # SC-03: solo con cuenta corriente. Activo, límite y saldo los valida el servicio (DEC-123).
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        widget=forms.HiddenInput,
        error_messages={"invalid_choice": "El cliente elegido ya no existe."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sin valor por defecto (DEC-51); con cuenta corriente desde H4 (DEC-41, S-3).
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


class AnularVentaForm(forms.Form):
    """Motivo de la anulación (DEC-66). Las reglas las aplica el servicio."""

    motivo = forms.CharField(
        label="Motivo de la anulación",
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 3, "class": "campo"}),
        error_messages={"required": "Escribí por qué se anula la venta."},
    )


class CajaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, caja):
        return (
            f"{caja.fecha:%d/%m/%Y} {caja.get_turno_display().lower()}, "
            f"caja N.º {caja.pk} ({caja.get_estado_display().lower()})"
        )


class HistorialVentasForm(forms.Form):
    """Filtros del historial de ventas (DEC-86). La consulta la hace el servicio."""

    desde = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    hasta = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    turno = forms.ChoiceField(
        label="Turno", required=False, choices=[("", "Todos"), *Turno.choices]
    )
    caja = CajaChoiceField(label="Caja", queryset=None, required=False, empty_label="Todas")
    todas = forms.BooleanField(label="Todas las ventas", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["caja"].queryset = cajas_para_filtrar()
        for nombre, campo in self.fields.items():
            campo.widget.attrs["class"] = "casilla" if nombre == "todas" else "campo"

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and hasta and desde > hasta:
            self.add_error("hasta", "La fecha hasta no puede ser anterior a la fecha desde.")
        return datos
