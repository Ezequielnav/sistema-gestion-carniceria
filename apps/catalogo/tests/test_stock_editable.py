"""Stock editable al crear y modificar productos, con ajuste registrado (DEC-98 a DEC-100).

CP-107 (modificar el stock), CP-108 (stock inicial) y CP-109 (panel).
"""

from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.catalogo.models import AjusteStock, MotivoAjuste, Producto, UnidadMedida
from apps.catalogo.services import crear_producto, modificar_producto

pytestmark = pytest.mark.django_db

NUEVO = reverse("catalogo:nuevo")


@pytest.fixture
def aceite(producto):
    producto.stock_actual = Decimal("10")
    producto.save()
    return producto


@pytest.fixture
def bondiola(categoria):
    return Producto.objects.create(
        nombre="Bondiola",
        categoria=categoria,
        precio_venta=Decimal("8900"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=True,
        stock_actual=Decimal("-1.250"),
    )


def _datos(producto, **cambios):
    datos = {
        "nombre": producto.nombre,
        "categoria": producto.categoria,
        "plus_interno": producto.plus_interno,
        "precio_venta": producto.precio_venta,
        "unidad_medida": producto.unidad_medida,
        "controla_stock": producto.controla_stock,
        "stock_minimo": producto.stock_minimo,
    }
    datos.update(cambios)
    return datos


def _editar(producto):
    return reverse("catalogo:editar", args=[producto.pk])


def _form(producto, **cambios):
    datos = {
        "nombre": producto.nombre,
        "categoria": producto.categoria.pk,
        "precio_venta": str(producto.precio_venta),
        "unidad_medida": producto.unidad_medida,
        "controla_stock": "on",
        "stock": str(producto.stock_actual),
        "stock_mostrado": str(producto.stock_actual),
        "motivo_ajuste": "",
    }
    datos.update(cambios)
    return datos


# CP-107: modificar el stock (servicio)


def test_cp107_cambiar_el_stock_lo_aplica_y_registra_el_ajuste(admin, aceite):
    modificar_producto(
        admin, aceite, _datos(aceite), stock=Decimal("7"), stock_mostrado=Decimal("10")
    )

    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("7")
    ajuste = AjusteStock.objects.get()
    assert (ajuste.stock_anterior, ajuste.stock_nuevo, ajuste.usuario, ajuste.producto) == (
        Decimal("10"),
        Decimal("7"),
        admin,
        aceite,
    )
    assert ajuste.motivo == MotivoAjuste.MODIFICACION_MANUAL and ajuste.fecha_hora


def test_cp107_el_motivo_elegido_se_guarda(admin, bondiola):
    modificar_producto(
        admin, bondiola, _datos(bondiola), Decimal("2.500"), Decimal("-1.250"), MotivoAjuste.ROTURA
    )

    bondiola.refresh_from_db()
    assert bondiola.stock_actual == Decimal("2.500")
    assert AjusteStock.objects.get().motivo == MotivoAjuste.ROTURA


def test_cp107_sin_cambio_de_stock_no_hay_ajuste(admin, aceite):
    modificar_producto(
        admin, aceite, _datos(aceite, precio_venta=Decimal("3000")), Decimal("10"), Decimal("10")
    )

    aceite.refresh_from_db()
    assert aceite.precio_venta == Decimal("3000") and aceite.stock_actual == Decimal("10")
    assert not AjusteStock.objects.exists()


def test_cp107_una_venta_mientras_se_editaba_no_se_deshace(admin, aceite):
    # El formulario mostró 10; mientras tanto se vendieron 2 (stock 8).
    Producto.objects.filter(pk=aceite.pk).update(stock_actual=Decimal("8"))
    aceite.refresh_from_db()

    modificar_producto(admin, aceite, _datos(aceite), Decimal("10"), Decimal("10"))

    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("8") and not AjusteStock.objects.exists()


@pytest.mark.parametrize(
    ("fixture", "stock"),
    [("aceite", "-1"), ("aceite", "1.5"), ("bondiola", "0.0005")],
)
def test_cp107_formato_del_stock(admin, request, fixture, stock):
    producto = request.getfixturevalue(fixture)
    antes = producto.stock_actual

    with pytest.raises(ValidationError) as error:
        modificar_producto(admin, producto, _datos(producto), Decimal(stock), antes)

    assert "stock" in error.value.message_dict
    producto.refresh_from_db()
    assert producto.stock_actual == antes and not AjusteStock.objects.exists()


def test_cp107_sin_control_de_stock_no_se_cambia(admin, aceite):
    with pytest.raises(ValidationError) as error:
        modificar_producto(
            admin, aceite, _datos(aceite, controla_stock=False), Decimal("3"), Decimal("10")
        )
    assert "stock" in error.value.message_dict


def test_cp107_solo_el_administrador_modifica(cajera_alta, aceite):
    with pytest.raises(PermissionDenied):
        modificar_producto(cajera_alta, aceite, _datos(aceite), Decimal("1"), Decimal("10"))


# CP-107: pantalla /productos/


def test_cp107_el_administrador_cambia_el_stock_desde_editar(client, admin, aceite):
    client.force_login(admin)
    pantalla = client.get(_editar(aceite))
    assert pantalla.context["form"]["stock"].value() == Decimal("10")
    assert 'value="10"' in pantalla.content.decode()
    assert "Modificación manual" in pantalla.content.decode()

    respuesta = client.post(_editar(aceite), _form(aceite, stock="7", motivo_ajuste="CONTEO"))

    assert respuesta.status_code == 302
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("7")
    assert AjusteStock.objects.get().motivo == MotivoAjuste.CONTEO


def test_cp107_el_error_de_stock_se_ve_junto_al_campo(client, admin, aceite):
    client.force_login(admin)

    respuesta = client.post(_editar(aceite), _form(aceite, stock="1.5"))

    assert "stock" in respuesta.context["form"].errors
    assert not AjusteStock.objects.exists()


def test_cp107_ya_no_hay_pantalla_de_ajuste_aparte(client, admin, aceite):
    client.force_login(admin)

    assert "Ajustar stock" not in client.get(reverse("catalogo:productos")).content.decode()
    assert client.get(f"/productos/{aceite.pk}/ajustar/").status_code == 404


# CP-108: stock inicial en el alta (DEC-99)


def _alta(**cambios):
    datos = {
        "nombre": "Yerba 1 kg",
        "precio_venta": "4200.00",
        "unidad_medida": "UNIDAD",
        "controla_stock": "on",
    }
    datos.update(cambios)
    return datos


def test_cp108_el_administrador_carga_stock_inicial(client, admin):
    client.force_login(admin)
    assert "Stock inicial" in client.get(NUEVO).content.decode()

    client.post(NUEVO, _alta(stock="12"))

    assert Producto.objects.get().stock_actual == Decimal("12")
    ajuste = AjusteStock.objects.get()
    assert (ajuste.motivo, ajuste.stock_anterior, ajuste.stock_nuevo, ajuste.usuario) == (
        MotivoAjuste.STOCK_INICIAL,
        Decimal("0"),
        Decimal("12"),
        admin,
    )


def test_cp108_sin_stock_inicial_arranca_en_0_sin_ajuste(client, admin):
    client.force_login(admin)

    client.post(NUEVO, _alta())

    assert Producto.objects.get().stock_actual == 0
    assert not AjusteStock.objects.exists()


def test_cp108_sin_control_de_stock_se_rechaza_junto_al_campo(client, admin):
    client.force_login(admin)
    datos = _alta(stock="5")
    del datos["controla_stock"]

    respuesta = client.post(NUEVO, datos)

    assert "stock" in respuesta.context["form"].errors
    assert not Producto.objects.exists()


def test_cp108_la_cajera_con_permiso_no_ve_el_stock_y_arranca_en_0(client, cajera_alta, aceite):
    client.force_login(cajera_alta)
    assert "Stock inicial" not in client.get(NUEVO).content.decode()

    client.post(NUEVO, _alta(stock="12"))

    assert Producto.objects.get(nombre="Yerba 1 kg").stock_actual == 0
    assert not AjusteStock.objects.exists()


def test_cp108_el_servicio_rechaza_stock_inicial_de_la_cajera(cajera_alta):
    with pytest.raises(PermissionDenied):
        crear_producto(cajera_alta, _alta(controla_stock=True), Decimal("12"))
    assert not Producto.objects.exists()


# CP-109: panel de administración (DEC-100)


@pytest.fixture
def cliente_panel(client, admin):
    admin.is_superuser = True
    admin.save()
    client.force_login(admin)
    return client


def _panel(**cambios):
    datos = {
        "nombre": "Yerba 1 kg",
        "precio_venta": "4200.00",
        "unidad_medida": "UNIDAD",
        "controla_stock": "on",
        "stock_actual": "0",
        "activo": "on",
    }
    datos.update(cambios)
    return datos


def test_cp109_alta_en_el_panel_con_stock_inicial_usa_el_servicio(cliente_panel, admin):
    respuesta = cliente_panel.post(
        reverse("admin:catalogo_producto_add"), _panel(stock_actual="12")
    )

    assert respuesta.status_code == 302
    producto = Producto.objects.get()
    assert producto.stock_actual == Decimal("12")
    assert AjusteStock.objects.get().motivo == MotivoAjuste.STOCK_INICIAL


def test_cp109_cambiar_el_stock_en_el_panel_registra_el_ajuste(cliente_panel, aceite):
    url = reverse("admin:catalogo_producto_change", args=[aceite.pk])
    datos = _panel(
        nombre=aceite.nombre,
        categoria=aceite.categoria.pk,
        precio_venta="2500.00",
        stock_actual="4",
        stock_mostrado="10",
        motivo_ajuste="VENCIMIENTO",
    )

    assert cliente_panel.post(url, datos).status_code == 302

    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("4")
    ajuste = AjusteStock.objects.get()
    assert (ajuste.stock_anterior, ajuste.motivo) == (Decimal("10"), MotivoAjuste.VENCIMIENTO)


def test_cp109_el_panel_rechaza_un_stock_invalido_junto_al_campo(cliente_panel, aceite):
    url = reverse("admin:catalogo_producto_change", args=[aceite.pk])
    datos = _panel(
        nombre=aceite.nombre, precio_venta="2500.00", stock_actual="1.5", stock_mostrado="10"
    )

    respuesta = cliente_panel.post(url, datos)

    errores = respuesta.context["adminform"].form.errors
    assert errores["stock_actual"] == [
        "Aceite 1 l se vende por unidad: el stock tiene que ser entero."
    ]
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("10") and not AjusteStock.objects.exists()


def test_cp109_un_ajuste_no_se_modifica_ni_se_borra_en_el_panel(cliente_panel, admin, aceite):
    modificar_producto(admin, aceite, _datos(aceite), Decimal("7"), Decimal("10"))
    ajuste = AjusteStock.objects.get()
    cambio = reverse("admin:catalogo_ajustestock_change", args=[ajuste.pk])
    borrado = reverse("admin:catalogo_ajustestock_delete", args=[ajuste.pk])

    assert cliente_panel.get(reverse("admin:catalogo_ajustestock_add")).status_code == 403
    cliente_panel.post(cambio, {"stock_nuevo": "0"})
    assert cliente_panel.post(borrado, {"post": "yes"}).status_code == 403
    listado = cliente_panel.get(reverse("admin:catalogo_ajustestock_changelist")).content.decode()
    assert ">10<" in listado and ">7<" in listado and "10,000" not in listado

    ajuste.refresh_from_db()
    assert ajuste.stock_nuevo == Decimal("7")
