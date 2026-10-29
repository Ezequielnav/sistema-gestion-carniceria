"""CU-15 Ajustar stock (CP-107) y stock inicial en el alta (CP-108). DEC-98 y DEC-99."""

from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.catalogo.models import AjusteStock, MotivoAjuste, Producto, UnidadMedida
from apps.catalogo.services import ajustar_stock, crear_producto

pytestmark = pytest.mark.django_db

LISTADO = reverse("catalogo:productos")
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


def _ajustar(producto):
    return reverse("catalogo:ajustar", args=[producto.pk])


# CP-107: servicio


def test_cp107_el_stock_queda_igual_al_contado_y_se_registra(admin, aceite):
    ajuste = ajustar_stock(admin, aceite, Decimal("7"), MotivoAjuste.ROTURA)

    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("7")
    assert (ajuste.stock_anterior, ajuste.stock_nuevo) == (Decimal("10"), Decimal("7"))
    assert (ajuste.motivo, ajuste.usuario, ajuste.producto) == (MotivoAjuste.ROTURA, admin, aceite)
    assert ajuste.fecha_hora is not None


def test_cp107_desde_stock_negativo_por_kg(admin, bondiola):
    ajuste = ajustar_stock(admin, bondiola, Decimal("2.500"), MotivoAjuste.CONTEO)

    bondiola.refresh_from_db()
    assert bondiola.stock_actual == Decimal("2.500")
    assert ajuste.stock_anterior == Decimal("-1.250")


def test_cp107_un_conteo_igual_al_stock_se_registra_sin_cambiarlo(admin, aceite):
    ajustar_stock(admin, aceite, Decimal("10"), MotivoAjuste.CONTEO)

    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("10")
    assert AjusteStock.objects.count() == 1


@pytest.mark.parametrize(
    ("producto_fixture", "contado", "campo"),
    [
        ("aceite", "-1", "stock_contado"),
        ("aceite", "1.5", "stock_contado"),
        ("bondiola", "0.0005", "stock_contado"),
    ],
)
def test_cp107_formato_del_stock_contado(admin, request, producto_fixture, contado, campo):
    producto = request.getfixturevalue(producto_fixture)
    antes = producto.stock_actual

    with pytest.raises(ValidationError) as error:
        ajustar_stock(admin, producto, Decimal(contado), MotivoAjuste.CONTEO)

    assert campo in error.value.message_dict
    producto.refresh_from_db()
    assert producto.stock_actual == antes and not AjusteStock.objects.exists()


def test_cp107_motivo_otro_exige_observacion_y_stock_inicial_no_se_elige(admin, aceite):
    with pytest.raises(ValidationError) as error:
        ajustar_stock(admin, aceite, Decimal("8"), MotivoAjuste.OTRO, "  ")
    assert "observacion" in error.value.message_dict

    with pytest.raises(ValidationError) as error:
        ajustar_stock(admin, aceite, Decimal("8"), MotivoAjuste.STOCK_INICIAL)
    assert "motivo" in error.value.message_dict

    ajustar_stock(admin, aceite, Decimal("8"), MotivoAjuste.OTRO, "Se lo llevó el dueño")
    assert AjusteStock.objects.get().observacion == "Se lo llevó el dueño"


def test_cp107_sin_control_de_stock_o_dado_de_baja_no_se_ajusta(admin, aceite):
    aceite.controla_stock = False
    aceite.save()
    with pytest.raises(ValidationError):
        ajustar_stock(admin, aceite, Decimal("1"), MotivoAjuste.CONTEO)

    aceite.controla_stock, aceite.activo = True, False
    aceite.save()
    with pytest.raises(ValidationError):
        ajustar_stock(admin, aceite, Decimal("1"), MotivoAjuste.CONTEO)


def test_cp107_solo_el_administrador_ajusta(cajera_alta, duenio, aceite):
    for usuario in (cajera_alta, duenio):
        with pytest.raises(PermissionDenied):
            ajustar_stock(usuario, aceite, Decimal("1"), MotivoAjuste.CONTEO)
    assert not AjusteStock.objects.exists()


# CP-107: pantalla


def test_cp107_el_administrador_ajusta_desde_el_listado(client, admin, aceite):
    client.force_login(admin)

    assert _ajustar(aceite) in client.get(LISTADO).content.decode()
    pantalla = client.get(_ajustar(aceite)).content.decode()
    assert "Stock actual" in pantalla and "Stock inicial" not in pantalla

    respuesta = client.post(_ajustar(aceite), {"stock_contado": "7", "motivo": "ROTURA"})

    assert respuesta.url == LISTADO
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("7")


def test_cp107_los_errores_se_ven_junto_al_campo(client, admin, aceite):
    client.force_login(admin)

    respuesta = client.post(_ajustar(aceite), {"stock_contado": "1.5", "motivo": "OTRO"})

    errores = respuesta.context["form"].errors
    assert "stock_contado" in errores and "observacion" in errores
    assert not AjusteStock.objects.exists()


def test_cp107_sin_control_de_stock_no_hay_boton_y_la_url_da_404(client, admin, aceite):
    aceite.controla_stock = False
    aceite.save()
    client.force_login(admin)

    assert _ajustar(aceite) not in client.get(LISTADO).content.decode()
    assert client.get(_ajustar(aceite)).status_code == 404


def test_cp107_la_cajera_y_los_duenios_reciben_403(client, cajera_alta, duenio, aceite):
    for usuario in (cajera_alta, duenio):
        client.force_login(usuario)
        assert client.get(_ajustar(aceite)).status_code == 403
        assert (
            client.post(_ajustar(aceite), {"stock_contado": "1", "motivo": "CONTEO"}).status_code
            == 403
        )
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("10")


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

    client.post(NUEVO, _alta(stock_inicial="12"))

    producto = Producto.objects.get()
    assert producto.stock_actual == Decimal("12")
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
    datos = _alta(stock_inicial="5")
    del datos["controla_stock"]

    respuesta = client.post(NUEVO, datos)

    assert "stock_inicial" in respuesta.context["form"].errors
    assert not Producto.objects.exists()


def test_cp108_la_cajera_con_permiso_no_ve_el_campo_y_arranca_en_0(client, cajera_alta):
    client.force_login(cajera_alta)
    assert "Stock inicial" not in client.get(NUEVO).content.decode()

    client.post(NUEVO, _alta(stock_inicial="12"))

    assert Producto.objects.get().stock_actual == 0
    assert not AjusteStock.objects.exists()


def test_cp108_el_servicio_rechaza_stock_inicial_de_la_cajera(cajera_alta):
    with pytest.raises(PermissionDenied):
        crear_producto(cajera_alta, _alta(controla_stock=True), Decimal("12"))
    assert not Producto.objects.exists()


# CP-109: los ajustes no se modifican ni se borran en el panel (RI-17)


def test_cp109_un_ajuste_no_se_modifica_ni_se_borra_en_el_panel(client, admin, aceite):
    admin.is_superuser = True
    admin.save()
    ajuste = ajustar_stock(admin, aceite, Decimal("7"), MotivoAjuste.ROTURA)
    client.force_login(admin)
    cambio = reverse("admin:catalogo_ajustestock_change", args=[ajuste.pk])
    borrado = reverse("admin:catalogo_ajustestock_delete", args=[ajuste.pk])

    assert client.get(cambio).status_code == 200
    listado = client.get(reverse("admin:catalogo_ajustestock_changelist")).content.decode()
    assert ">10<" in listado and ">7<" in listado and "10,000" not in listado
    client.post(cambio, {"stock_nuevo": "0"})
    assert client.post(borrado, {"post": "yes"}).status_code == 403

    ajuste.refresh_from_db()
    assert ajuste.stock_nuevo == Decimal("7")
