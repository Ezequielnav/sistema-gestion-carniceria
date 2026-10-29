from decimal import Decimal

import pytest
from django.apps import apps
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.caja.models import MedioPago
from apps.catalogo.models import Producto
from apps.proveedores.models import DetalleIngreso, IngresoMercaderia
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import DetalleVenta, EstadoVenta, Venta

APPS_DEL_SISTEMA = ["usuarios", "caja", "ventas", "catalogo", "proveedores", "clientes"]
# Los renglones se ven dentro de su venta o su ingreso, sin módulo propio.
RENGLONES = {"detalle_venta", "detalle_ingreso"}
MODELOS = [
    m
    for app in APPS_DEL_SISTEMA
    for m in apps.get_app_config(app).get_models()
    if m._meta.db_table not in RENGLONES
]


@pytest.fixture
def cliente_admin(client, db):
    admin = Usuario.objects.create_superuser(
        username="admin",
        password="clave-de-prueba-123",
        nombre_completo="Admin",
        rol=Rol.ADMINISTRADOR,
    )
    client.force_login(admin)
    return client, admin


def test_el_panel_usa_el_nombre_y_los_estilos_del_negocio(cliente_admin):
    client, _ = cliente_admin

    contenido = client.get(reverse("admin:index")).content.decode()

    assert "Carnicería Rojano" in contenido
    assert "unfold" in contenido
    assert "css/admin.css" in contenido


# DEC-31: los registros operativos se crean solo desde su caso de uso.
SOLO_LECTURA = {
    "caja",
    "cierre_caja_detalle",
    "movimiento_caja",
    "venta",
    "pago_cliente",
    "movimiento_cuenta_corriente",
    "ingreso_mercaderia",
    "pago_proveedor",
}
EDITABLES = [m for m in MODELOS if m._meta.db_table not in SOLO_LECTURA]
OPERATIVOS = [m for m in MODELOS if m._meta.db_table in SOLO_LECTURA]


def _url(modelo, vista, *args):
    opciones = modelo._meta
    return reverse(f"admin:{opciones.app_label}_{opciones.model_name}_{vista}", args=args)


@pytest.mark.parametrize("modelo", EDITABLES, ids=lambda m: m._meta.db_table)
def test_cada_modelo_editable_tiene_listado_y_alta_en_el_panel(cliente_admin, modelo):
    client, _ = cliente_admin

    assert client.get(_url(modelo, "changelist")).status_code == 200
    assert client.get(_url(modelo, "add")).status_code == 200


@pytest.mark.parametrize("modelo", OPERATIVOS, ids=lambda m: m._meta.db_table)
def test_los_registros_operativos_se_consultan_pero_no_se_cargan_en_el_panel(cliente_admin, modelo):
    client, _ = cliente_admin

    assert client.get(_url(modelo, "changelist")).status_code == 200
    assert client.get(_url(modelo, "add")).status_code == 403
    assert client.post(_url(modelo, "add"), {}).status_code == 403
    assert not modelo.objects.exists()


def test_una_venta_se_ve_en_el_panel_sin_poder_modificarla_ni_borrarla(cliente_admin, venta):
    client, _ = cliente_admin
    monto_original = venta.monto_total

    assert client.get(_url(Venta, "change", venta.pk)).status_code == 200
    client.post(_url(Venta, "change", venta.pk), {"monto_total": "0"})
    assert client.post(_url(Venta, "delete", venta.pk), {"post": "yes"}).status_code == 403

    venta.refresh_from_db()
    assert venta.monto_total == monto_original


def test_un_ingreso_se_ve_en_el_panel_sin_poder_modificarlo_ni_borrarlo(cliente_admin, ingreso):
    client, _ = cliente_admin
    total_original = ingreso.total

    assert client.get(_url(IngresoMercaderia, "change", ingreso.pk)).status_code == 200
    client.post(_url(IngresoMercaderia, "change", ingreso.pk), {"total": "0"})
    assert (
        client.post(_url(IngresoMercaderia, "delete", ingreso.pk), {"post": "yes"}).status_code
        == 403
    )

    ingreso.refresh_from_db()
    assert ingreso.total == total_original


def test_precio_negativo_muestra_el_error_junto_al_campo(cliente_admin, categoria):
    client, _ = cliente_admin
    datos = {
        "nombre": "Prueba",
        "categoria": categoria.pk,
        "precio_venta": "-5",
        "unidad_medida": "UNIDAD",
        "controla_stock": "on",
        "activo": "on",
    }

    respuesta = client.post(_url(Producto, "add"), datos)

    assert respuesta.status_code == 200
    assert respuesta.context["adminform"].form.errors == {
        "precio_venta": ["No puede ser negativo."]
    }
    assert not Producto.objects.exists()


def test_el_formulario_de_producto_marca_minimos_y_no_edita_el_stock(cliente_admin):
    client, _ = cliente_admin

    formulario = client.get(_url(Producto, "add")).context["adminform"].form

    assert formulario.fields["precio_venta"].widget.attrs["min"] == "0"
    assert formulario.fields["stock_minimo"].widget.attrs["min"] == "0"
    assert "stock_actual" not in formulario.fields


def test_medio_de_pago_repetido_con_otras_mayusculas_muestra_un_mensaje_claro(
    cliente_admin, efectivo
):
    client, _ = cliente_admin

    respuesta = client.post(_url(MedioPago, "add"), {"nombre": "EFECTIVO", "activo": "on"})

    assert "Ya existe un medio de pago con ese nombre." in respuesta.content.decode()
    assert MedioPago.objects.count() == 1


def test_la_ficha_de_un_usuario_abre_en_el_panel(cliente_admin):
    client, admin = cliente_admin

    respuesta = client.get(reverse("admin:usuarios_usuario_change", args=[admin.pk]))

    assert respuesta.status_code == 200


# DEC-32: los permisos salen del rol; Grupos y permisos individuales no están en el panel.
def test_el_panel_no_tiene_grupos_ni_permisos_individuales(cliente_admin):
    client, admin = cliente_admin

    with pytest.raises(NoReverseMatch):
        reverse("admin:auth_group_changelist")

    formulario = (
        client.get(reverse("admin:usuarios_usuario_change", args=[admin.pk]))
        .context["adminform"]
        .form
    )
    assert "groups" not in formulario.fields
    assert "user_permissions" not in formulario.fields


def _bloques(respuesta):
    return [nombre for nombre, _ in respuesta.context["adminform"].fieldsets]


def test_una_venta_confirmada_no_muestra_el_bloque_de_anulacion(cliente_admin, venta):
    client, _ = cliente_admin

    respuesta = client.get(_url(Venta, "change", venta.pk))

    assert _bloques(respuesta) == ["Venta"]
    contenido = respuesta.content.decode()
    assert "+00:00" not in contenido
    assert "Fecha y hora de la venta" in contenido
    assert "Medio de pago" in contenido
    assert "Motivo de anulación" not in contenido


def test_una_venta_anulada_muestra_el_bloque_de_anulacion(cliente_admin, venta):
    client, admin = cliente_admin
    Venta.objects.filter(pk=venta.pk).update(
        estado=EstadoVenta.ANULADA,
        anulada_en=timezone.now(),
        anulada_por_usuario=admin,
        motivo_anulacion="Cobro duplicado",
    )

    respuesta = client.get(_url(Venta, "change", venta.pk))

    assert _bloques(respuesta) == ["Venta", "Anulación"]
    contenido = respuesta.content.decode()
    for etiqueta in ("Fecha y hora de anulación", "Anulada por", "Motivo de anulación"):
        assert etiqueta in contenido
    assert "Cobro duplicado" in contenido


def test_los_productos_se_listan_dentro_de_la_venta_sin_poder_editarlos(
    cliente_admin, venta, producto
):
    client, _ = cliente_admin
    DetalleVenta.objects.create(
        venta=venta,
        producto=producto,
        cantidad=Decimal("1"),
        precio_unitario=Decimal("2500.00"),
        subtotal=Decimal("2500.00"),
    )

    respuesta = client.get(_url(Venta, "change", venta.pk))

    (renglones,) = respuesta.context["inline_admin_formsets"]
    assert renglones.formset.model is DetalleVenta
    assert not renglones.has_add_permission
    assert not renglones.has_change_permission
    assert not renglones.has_delete_permission
    assert "Aceite 1 l" in respuesta.content.decode()


def test_los_productos_se_listan_dentro_del_ingreso(cliente_admin, ingreso, producto):
    client, _ = cliente_admin
    DetalleIngreso.objects.create(
        ingreso=ingreso,
        producto=producto,
        cantidad=Decimal("2"),
        precio_unitario=Decimal("2500.00"),
    )

    respuesta = client.get(_url(IngresoMercaderia, "change", ingreso.pk))

    (renglones,) = respuesta.context["inline_admin_formsets"]
    assert renglones.formset.model is DetalleIngreso
    assert not renglones.has_change_permission
    assert "Aceite 1 l" in respuesta.content.decode()


@pytest.mark.parametrize("modelo", [DetalleVenta, DetalleIngreso], ids=lambda m: m._meta.db_table)
def test_los_renglones_no_tienen_modulo_propio_en_el_panel(modelo):
    with pytest.raises(NoReverseMatch):
        _url(modelo, "changelist")
