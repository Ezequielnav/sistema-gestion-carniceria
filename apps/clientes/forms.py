from django import forms
from django.forms.models import fields_for_model

from apps.clientes.models import Cliente
from apps.clientes.services import CAMPOS_EDITABLES
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


class ClienteForm(forms.Form):
    """Datos de un cliente (CU-12, DEC-117). Las reglas las aplica el servicio."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(
            fields_for_model(
                Cliente,
                fields=CAMPOS_EDITABLES,
                labels=ETIQUETAS,
                help_texts=AYUDAS,
                widgets={"observaciones": forms.Textarea(attrs={"rows": 3})},
            )
        )
        # Repite el CHECK de la base para mostrar el error junto al campo (RI-16).
        self.fields["limite_credito"].validators.append(NO_NEGATIVO)
        self.fields["limite_credito"].widget.attrs.update({"min": "0", "step": "0.01"})
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"
