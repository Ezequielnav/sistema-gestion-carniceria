from django import forms
from django.forms.models import fields_for_model

from apps.caja.models import MedioPago
from apps.clientes.models import Cliente
from apps.clientes.services import CAMPOS_EDITABLES, medios_para_cobrar
from apps.comun.models import NO_NEGATIVO

ETIQUETAS = {
    "nombre": "Nombre",
    "telefono": "Teléfono",
    "direccion": "Dirección",
    "limite_credito": "Límite de crédito",
    "observaciones": "Observaciones",
}
AYUDAS = {
    "telefono": "Opcional.",
    "direccion": "Opcional.",
    # DEC-108 y DEC-115.
    "limite_credito": "Vacío: sin límite. 0: sin crédito habilitado.",
    "observaciones": "Opcional. Notas y condiciones de crédito; no cambian el saldo.",
}


def _campos_de_cliente(nombres):
    """Campos del modelo con etiquetas, ayudas y el mínimo del límite (DEC-115, DEC-117)."""
    campos = fields_for_model(
        Cliente,
        fields=nombres,
        labels=ETIQUETAS,
        help_texts=AYUDAS,
        widgets={"observaciones": forms.Textarea(attrs={"rows": 3})},
    )
    # Repite el CHECK de la base para mostrar el error junto al campo (RI-16).
    campos["limite_credito"].validators.append(NO_NEGATIVO)
    campos["limite_credito"].widget.attrs.update({"min": "0", "step": "0.01"})
    for campo in campos.values():
        campo.widget.attrs["class"] = "campo"
    return campos


class ClienteForm(forms.Form):
    """Datos de un cliente (CU-12, DEC-117). Las reglas las aplica el servicio."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(_campos_de_cliente(CAMPOS_EDITABLES))


class CobroForm(forms.Form):
    """Cobro de cuenta corriente (CU-04). Saldo, caja y permisos los valida el servicio."""

    # SC-01: lo completa la pantalla al elegir el cliente.
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        widget=forms.HiddenInput,
        error_messages={
            "required": "Elegí el cliente al que le cobrás.",
            "invalid_choice": "El cliente elegido ya no existe.",
        },
    )
    monto = forms.DecimalField(
        label="Monto",
        max_digits=12,
        decimal_places=2,
        error_messages={"required": "Escribí el monto que se cobra."},
    )
    # Sin valor por defecto (como DEC-51) y sin cuenta corriente (DEC-110).
    medio_pago = forms.ModelChoiceField(
        queryset=MedioPago.objects.none(),
        label="Medio de pago",
        empty_label="Elegí un medio de pago",
        error_messages={
            "required": "Elegí un medio de pago.",
            "invalid_choice": "Ese medio de pago no se puede usar para cobrar.",
        },
    )
    # S-6 (DEC-125): solo la ve el Administrador, marcada si hay caja abierta de hoy.
    entra_a_caja = forms.BooleanField(
        label="Entra a la caja abierta",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "casilla"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["medio_pago"].queryset = medios_para_cobrar()
        self.fields["medio_pago"].widget.attrs["class"] = "campo"
        self.fields["monto"].widget.attrs.update({"class": "campo", "min": "0.01", "step": "0.01"})


class AnularCobroForm(forms.Form):
    """Motivo de la anulación del cobro (DEC-113). Las reglas las aplica el servicio."""

    motivo = forms.CharField(
        label="Motivo de la anulación",
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 3, "class": "campo"}),
        error_messages={"required": "Escribí por qué se anula el cobro."},
    )


class CondicionesForm(forms.Form):
    """Límite de crédito y observaciones desde el estado de cuenta (CU-08, RF-41)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(_campos_de_cliente(["limite_credito", "observaciones"]))


class SaldoInicialForm(forms.Form):
    """Deuda que el cliente ya tenía al empezar (DEC-119). Las reglas las aplica el servicio."""

    monto = forms.DecimalField(
        label="Monto",
        max_digits=12,
        decimal_places=2,
        error_messages={"required": "Escribí el monto que debe."},
        widget=forms.NumberInput(attrs={"class": "campo", "min": "0.01", "step": "0.01"}),
    )
    fecha_origen = forms.DateField(
        label="Fecha de origen",
        help_text="Desde cuándo la debe: cuenta para la deuda vencida.",
        error_messages={"required": "Indicá la fecha de origen de la deuda."},
        widget=forms.DateInput(attrs={"type": "date", "class": "campo"}, format="%Y-%m-%d"),
    )
    motivo = forms.CharField(
        label="Motivo",
        max_length=255,
        help_text="Por ejemplo, de dónde sale el monto (libreta, planilla).",
        error_messages={"required": "Escribí el motivo del saldo inicial."},
        widget=forms.TextInput(attrs={"class": "campo"}),
    )


class AnularSaldoInicialForm(forms.Form):
    """Motivo de la anulación del saldo inicial (DEC-119)."""

    motivo = forms.CharField(
        label="Motivo de la anulación",
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 2, "class": "campo"}),
        error_messages={"required": "Escribí por qué se anula el saldo inicial."},
    )
