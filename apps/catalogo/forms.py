from django import forms
from django.forms.models import fields_for_model

from apps.catalogo.models import AjusteStock, Producto, UnidadMedida
from apps.catalogo.services import CAMPOS_EDITABLES, MOTIVOS_DE_AJUSTE

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

    def __init__(self, *args, con_stock_inicial=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(
            fields_for_model(Producto, fields=CAMPOS_EDITABLES, labels=ETIQUETAS, help_texts=AYUDAS)
        )
        # DEC-99: solo en el alta del Administrador; la cajera no ve el stock (DEC-33).
        if con_stock_inicial:
            self.fields["stock_inicial"] = forms.DecimalField(
                label="Stock inicial",
                required=False,
                min_value=0,
                max_digits=12,
                decimal_places=3,
                help_text="Opcional, solo si controla stock. Queda registrado como ajuste.",
            )
        self.fields["categoria"].empty_label = "Sin categoría"
        # Sin unidad por defecto: la primera opción no es válida y obliga a elegir (PR-03).
        self.fields["unidad_medida"].choices = [("", "Elegí una unidad"), *UnidadMedida.choices]
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "casilla"
            else:
                campo.widget.attrs["class"] = "campo"
        # Mínimo del navegador; la regla la valida el servicio (RI-16).
        self.fields["precio_venta"].widget.attrs["min"] = "0"
        self.fields["stock_minimo"].widget.attrs["min"] = "0"
        if con_stock_inicial:
            self.fields["stock_inicial"].widget.attrs["min"] = "0"


class AjusteStockForm(forms.Form):
    """CU-15. Las reglas (RI-17, DEC-79, DEC-98) las aplica el servicio."""

    stock_contado = AjusteStock._meta.get_field("stock_nuevo").formfield(
        label="Stock contado", min_value=0
    )
    motivo = forms.ChoiceField(
        label="Motivo",
        choices=[("", "Elegí un motivo"), *[(m.value, m.label) for m in MOTIVOS_DE_AJUSTE]],
    )
    observacion = forms.CharField(
        label="Observación",
        required=False,
        max_length=255,
        help_text="Obligatoria si el motivo es «Otro».",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, producto, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"
        paso = "0.001" if producto.unidad_medida == UnidadMedida.KG else "1"
        self.fields["stock_contado"].widget.attrs.update(
            {"min": "0", "step": paso, "autofocus": True}
        )
