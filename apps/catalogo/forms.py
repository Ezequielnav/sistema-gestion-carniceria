from django import forms
from django.forms.models import fields_for_model

from apps.catalogo.models import MotivoAjuste, Producto, UnidadMedida
from apps.catalogo.services import CAMPOS_EDITABLES, MOTIVOS_DE_MODIFICACION

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


def campos_de_stock(es_alta):
    """Stock editable del Administrador (DEC-98, DEC-99), para la pantalla y el panel.

    Al modificar, `stock_mostrado` guarda el stock que vio el Administrador: el servicio
    registra un ajuste solo si lo cambió, aunque haya habido ventas mientras editaba.
    """
    stock = forms.DecimalField(
        label="Stock inicial" if es_alta else "Stock",
        required=False,
        max_digits=12,
        decimal_places=3,
        help_text=(
            "Opcional, solo si controla stock. Queda registrado como ajuste."
            if es_alta
            else "Si lo cambiás, queda registrado como ajuste con el motivo elegido."
        ),
    )
    if es_alta:
        return {"stock": stock}
    return {
        "stock": stock,
        "motivo_ajuste": forms.ChoiceField(
            label="Motivo del cambio de stock",
            required=False,
            choices=[(m.value, m.label) for m in MOTIVOS_DE_MODIFICACION],
            initial=MotivoAjuste.MODIFICACION_MANUAL,
        ),
        "stock_mostrado": forms.DecimalField(
            required=False, max_digits=12, decimal_places=3, widget=forms.HiddenInput
        ),
    }


class ProductoForm(forms.Form):
    """Datos de un producto. Las reglas (RN-05, A1, RI-16, RI-07) las aplica el servicio."""

    def __init__(self, *args, con_stock=False, es_alta=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(
            fields_for_model(Producto, fields=CAMPOS_EDITABLES, labels=ETIQUETAS, help_texts=AYUDAS)
        )
        # DEC-98, DEC-99 y DEC-103: solo el Administrador carga y cambia el stock.
        if con_stock:
            self.fields.update(campos_de_stock(es_alta))
        self.fields["categoria"].empty_label = "Sin categoría"
        # Sin unidad por defecto: la primera opción no es válida y obliga a elegir (DEC-79).
        self.fields["unidad_medida"].choices = [("", "Elegí una unidad"), *UnidadMedida.choices]
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "casilla"
            else:
                campo.widget.attrs["class"] = "campo"
        # Mínimo del navegador; la regla la valida el servicio (RI-16).
        self.fields["precio_venta"].widget.attrs["min"] = "0"
        self.fields["stock_minimo"].widget.attrs["min"] = "0"
        if con_stock:
            self.fields["stock"].widget.attrs.update({"min": "0", "step": "0.001"})
