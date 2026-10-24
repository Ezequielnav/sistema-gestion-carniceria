from django import forms
from django.forms.models import fields_for_model

from apps.catalogo.models import Producto
from apps.catalogo.services import CAMPOS_EDITABLES

ETIQUETAS = {
    "nombre": "Nombre",
    "categoria": "Categoría",
    "plus_interno": "Plus interno",
    "precio_venta": "Precio de venta",
    "unidad_medida": "Unidad de medida",
    "controla_stock": "Controla stock",
    "stock_minimo": "Stock mínimo",
}

AYUDAS = {
    "plus_interno": "Opcional. Código interno de la carnicería; no se puede repetir.",
    "controla_stock": "Desmarcalo para los productos que no llevan stock, como la carne.",
    "stock_minimo": "Opcional. Cantidad desde la que se avisa que falta mercadería.",
}


class ProductoForm(forms.Form):
    """Datos de un producto. Las reglas (RN-05, A1, RI-16, RI-07) las aplica el servicio."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(
            fields_for_model(Producto, fields=CAMPOS_EDITABLES, labels=ETIQUETAS, help_texts=AYUDAS)
        )
        self.fields["categoria"].empty_label = "Sin categoría"
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "casilla"
            else:
                campo.widget.attrs["class"] = "campo"
        # Mínimo del navegador; la regla la valida el servicio (RI-16).
        self.fields["precio_venta"].widget.attrs["min"] = "0"
        self.fields["stock_minimo"].widget.attrs["min"] = "0"
