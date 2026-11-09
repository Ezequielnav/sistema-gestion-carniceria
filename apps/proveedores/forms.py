import json
from decimal import Decimal, InvalidOperation

from django import forms
from django.forms.models import fields_for_model

from apps.caja.models import MedioPago
from apps.comun.forms import RangoFechasForm
from apps.comun.models import pesos
from apps.proveedores.models import CondicionPago, IngresoMercaderia, Proveedor
from apps.proveedores.services import (
    CAMPOS_EDITABLES,
    deudas_para_pagar,
    medios_para_pagar,
    proveedores_para_ingreso,
    saldo_de_ingreso,
)


def _sale_de_caja():
    """Solo se muestra en efectivo (DEC-106); marcada por defecto."""
    return forms.BooleanField(
        label="Sale de la caja abierta",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "casilla"}),
    )


def _id_del_efectivo():
    return MedioPago.objects.filter(es_efectivo=True).values_list("pk", flat=True).first()


ETIQUETAS = {"nombre": "Nombre", "telefono": "Teléfono", "email": "Email"}
AYUDAS = {
    "telefono": "Opcional.",
    "email": "Opcional.",
}


class ProveedorForm(forms.Form):
    """Datos de un proveedor (CU-13). Las reglas las aplica el servicio."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(
            fields_for_model(
                Proveedor, fields=CAMPOS_EDITABLES, labels=ETIQUETAS, help_texts=AYUDAS
            )
        )
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"


class ConfirmarIngresoForm(forms.Form):
    """Proveedor, remito y líneas del ingreso (CU-05). Las reglas las aplica el servicio."""

    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.none(),
        label="Proveedor",
        empty_label="Elegí un proveedor",
        error_messages={
            "required": "Elegí un proveedor.",
            "invalid_choice": "Ese proveedor no está activo.",
        },
    )
    observacion = forms.CharField(label="Remito u observación", max_length=255, required=False)
    condicion_pago = forms.ChoiceField(
        label="Condición",
        choices=CondicionPago.choices,
        initial=CondicionPago.A_CREDITO,
        required=False,
    )
    # Solo al contado: el pago por el total se registra en la misma operación (DEC-81).
    medio_pago = forms.ModelChoiceField(
        queryset=MedioPago.objects.none(),
        label="Medio de pago",
        required=False,
        empty_label="Elegí un medio",
    )
    sale_de_caja = _sale_de_caja()
    # Lista en JSON: [{"producto": id, "cantidad": "1.250", "precio": "1800.00"}].
    lineas = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = proveedores_para_ingreso()
        self.fields["medio_pago"].queryset = medios_para_pagar()
        self.id_efectivo = _id_del_efectivo()
        for nombre, campo in self.fields.items():
            if nombre != "sale_de_caja":
                campo.widget.attrs["class"] = "campo"

    def clean_condicion_pago(self):
        return self.cleaned_data["condicion_pago"] or CondicionPago.A_CREDITO

    def clean_lineas(self):
        try:
            datos = json.loads(self.cleaned_data["lineas"] or "[]")
            lineas = [
                (int(d["producto"]), Decimal(str(d["cantidad"])), Decimal(str(d["precio"])))
                for d in datos
            ]
        except (ValueError, TypeError, KeyError, InvalidOperation) as error:
            raise forms.ValidationError("La lista de productos no es válida.") from error
        if not all(c.is_finite() and p.is_finite() for _, c, p in lineas):
            raise forms.ValidationError("La lista de productos no es válida.")
        return lineas


class AnularIngresoForm(forms.Form):
    """Motivo de la anulación (DEC-92). Las reglas las aplica el servicio."""

    motivo = forms.CharField(
        label="Motivo de la anulación",
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 3, "class": "campo"}),
        error_messages={"required": "Escribí por qué se anula el ingreso."},
    )


def _saldo(ingreso):
    # L10 (DEC-164): el saldo viene calculado en la consulta de las opciones.
    saldo = getattr(ingreso, "saldo", None)
    return saldo_de_ingreso(ingreso) if saldo is None else saldo


class IngresoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, ingreso):
        return (
            f"{ingreso.proveedor} · ingreso N.º {ingreso.pk} del {ingreso.fecha:%d/%m/%Y} · "
            f"saldo {pesos(_saldo(ingreso))}"
        )


class PagoForm(forms.Form):
    """CU-07: deuda, monto y medio. Las reglas (RI-08, RI-09, DEC-80) las aplica el servicio."""

    ingreso = IngresoChoiceField(
        queryset=IngresoMercaderia.objects.none(),
        label="Deuda (ingreso con saldo)",
        empty_label="Elegí un ingreso",
        error_messages={
            "required": "Elegí el ingreso que se paga.",
            "invalid_choice": "Ese ingreso no tiene saldo pendiente.",
        },
    )
    monto = forms.DecimalField(label="Monto", max_digits=12, decimal_places=2, min_value=0)
    medio_pago = forms.ModelChoiceField(
        queryset=MedioPago.objects.none(),
        label="Medio de pago",
        empty_label="Elegí un medio",
        error_messages={"required": "Elegí el medio de pago."},
    )
    sale_de_caja = _sale_de_caja()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ingreso"].queryset = deudas_para_pagar()
        self.fields["medio_pago"].queryset = medios_para_pagar()
        self.id_efectivo = _id_del_efectivo()
        for nombre, campo in self.fields.items():
            if nombre != "sale_de_caja":
                campo.widget.attrs["class"] = "campo"
        self.fields["monto"].widget.attrs.update({"min": "0.01", "step": "0.01"})


class AnularPagoForm(forms.Form):
    """Motivo de la anulación del pago (DEC-92). Las reglas las aplica el servicio."""

    motivo = forms.CharField(
        label="Motivo de la anulación",
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 3, "class": "campo"}),
        error_messages={"required": "Escribí por qué se anula el pago."},
    )


class ProveedorElegido(forms.ModelChoiceField):
    def label_from_instance(self, proveedor):
        return proveedor.nombre if proveedor.activo else f"{proveedor.nombre} (dado de baja)"


class FiltroListadoForm(RangoFechasForm):
    """Filtro de los listados de ingresos y pagos (DEC-139, DEC-152): fechas opcionales con la
    validación de CU-09 (DEC-145) y proveedor, también uno dado de baja."""

    proveedor = ProveedorElegido(
        label="Proveedor",
        queryset=Proveedor.objects.order_by("nombre", "pk"),
        required=False,
        empty_label="Todos",
    )
