import pytest
from django.apps import apps
from django.urls import reverse

from apps.caja.models import MedioPago
from apps.catalogo.models import Producto
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import Venta

APPS_DEL_SISTEMA = ["usuarios", "caja", "ventas", "catalogo", "proveedores", "clientes"]
MODELOS = [m for app in APPS_DEL_SISTEMA for m in apps.get_app_config(app).get_models()]


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
    "detalle_venta",
    "pago_cliente",
    "movimiento_cuenta_corriente",
    "ingreso_mercaderia",
    "detalle_ingreso",
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
