from django import forms
from django.forms.models import fields_for_model

from apps.proveedores.models import Proveedor
from apps.proveedores.services import CAMPOS_EDITABLES

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
