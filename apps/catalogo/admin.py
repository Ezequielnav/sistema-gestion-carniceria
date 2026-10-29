from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from unfold.widgets import UnfoldAdminSelectWidget

from apps.catalogo.models import AjusteStock, Categoria, MotivoAjuste, Producto, formatear_cantidad
from apps.catalogo.services import (
    CAMPOS_EDITABLES,
    MOTIVOS_DE_MODIFICACION,
    crear_producto,
    dar_de_baja,
    modificar_producto,
    reactivar,
    stock_cambiado,
    validar_stock_editado,
)
from apps.comun.admin import AdminBase, SoloLecturaAdmin


@admin.register(Categoria)
class CategoriaAdmin(AdminBase):
    list_display = ("nombre",)
    search_fields = ("nombre",)


class ProductoAdminForm(forms.ModelForm):
    """Stock editable como en /productos/ (DEC-98, DEC-99): lo valida el servicio de catálogo."""

    motivo_ajuste = forms.ChoiceField(
        label="Motivo del cambio de stock",
        required=False,
        choices=[(m.value, m.label) for m in MOTIVOS_DE_MODIFICACION],
        initial=MotivoAjuste.MODIFICACION_MANUAL,
        widget=UnfoldAdminSelectWidget,
        help_text="Si cambiás el stock, queda registrado como ajuste con este motivo.",
    )
    # Stock que vio el Administrador; el ajuste se registra solo si lo cambió (DEC-98).
    stock_mostrado = forms.DecimalField(
        required=False, max_digits=12, decimal_places=3, widget=forms.HiddenInput
    )

    class Meta:
        model = Producto
        fields = [*CAMPOS_EDITABLES, "stock_actual", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["stock_mostrado"].initial = self.instance.stock_actual
        else:
            self.fields["stock_actual"].label = "Stock inicial"

    def clean(self):
        datos = super().clean()
        if "stock_actual" not in datos:
            return datos
        producto = Producto(
            nombre=datos.get("nombre", ""),
            unidad_medida=datos.get("unidad_medida"),
            controla_stock=datos.get("controla_stock"),
            stock_actual=self.instance.stock_actual if self.instance.pk else 0,
        )
        stock = datos["stock_actual"]
        if stock_cambiado(producto, stock, datos.get("stock_mostrado")):
            try:
                validar_stock_editado(producto, stock)
            except ValidationError as error:
                self.add_error("stock_actual", error.message_dict["stock"])
        return datos


@admin.register(Producto)
class ProductoAdmin(AdminBase):
    form = ProductoAdminForm
    list_display = ("nombre", "plus_interno", "categoria", "precio_venta", "stock_actual", "activo")
    list_filter = ("activo", "controla_stock", "categoria")
    search_fields = ("nombre", "plus_interno")

    def get_fields(self, request, obj=None):
        campos = super().get_fields(request, obj)
        # En el alta el motivo es siempre "Stock inicial" (DEC-99).
        return campos if obj else [c for c in campos if c != "motivo_ajuste"]

    def save_model(self, request, obj, form, change):
        """Guarda con el servicio de catálogo, como /productos/: el stock cambia con
        mover_stock y queda registrado como ajuste (RI-07, RI-17, DEC-100)."""
        datos = form.cleaned_data
        if change:
            producto = Producto.objects.get(pk=obj.pk)
            modificar_producto(
                request.user,
                producto,
                datos,
                stock=datos["stock_actual"],
                stock_mostrado=datos.get("stock_mostrado"),
                motivo=datos.get("motivo_ajuste") or None,
            )
        else:
            producto = crear_producto(request.user, datos, stock=datos["stock_actual"])
        if producto.activo != datos["activo"]:
            (reactivar if datos["activo"] else dar_de_baja)(request.user, producto)
        obj.pk = producto.pk
        obj._state.adding = False
        obj.refresh_from_db()


@admin.register(AjusteStock)
class AjusteStockAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "producto", "anterior", "nuevo", "motivo", "usuario")
    list_filter = ("motivo",)
    search_fields = ("producto__nombre",)
    fields = ("fecha_hora", "producto", "usuario", "anterior", "nuevo", "motivo")
    readonly_fields = ("anterior", "nuevo")

    # DEC-48: "2" por unidad y "1,250 kg" por kg, como en el resto del sistema.
    @admin.display(description="Stock anterior")
    def anterior(self, obj):
        return formatear_cantidad(obj.stock_anterior, obj.producto.unidad_medida)

    @admin.display(description="Stock nuevo")
    def nuevo(self, obj):
        return formatear_cantidad(obj.stock_nuevo, obj.producto.unidad_medida)
