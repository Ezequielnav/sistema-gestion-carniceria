"""CU-11 de punta a punta: pantallas de /productos/ por rol (CP-53, CP-55, CP-56, CP-57, CP-59)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalogo.models import Producto

pytestmark = pytest.mark.django_db

LISTADO = reverse("catalogo:productos")
NUEVO = reverse("catalogo:nuevo")


def _form(**cambios):
    datos = {
        "nombre": "Yerba 1 kg",
        "plus_interno": "700",
        "precio_venta": "4200.00",
        "unidad_medida": "UNIDAD",
        "controla_stock": "on",
        "stock_minimo": "5",
    }
    datos.update(cambios)
    return datos


def _editar(producto):
    return reverse("catalogo:editar", args=[producto.pk])


def _baja(producto):
    return reverse("catalogo:baja", args=[producto.pk])


# Administrador: flujo completo


def test_admin_da_de_alta_edita_y_da_de_baja(client, admin, categoria):
    client.force_login(admin)

    respuesta = client.post(NUEVO, _form(categoria=categoria.pk))
    assert respuesta.url == LISTADO
    producto = Producto.objects.get(plus_interno="700")
    assert producto.stock_actual == 0 and producto.categoria == categoria

    client.post(_editar(producto), _form(nombre="Yerba 500 g", precio_venta="2300"))
    producto.refresh_from_db()
    assert producto.nombre == "Yerba 500 g" and producto.precio_venta == Decimal("2300")

    assert client.get(_baja(producto)).status_code == 200
    client.post(_baja(producto))
    producto.refresh_from_db()
    assert not producto.activo


def test_admin_ve_stock_y_acciones(client, admin, producto):
    client.force_login(admin)

    contenido = client.get(LISTADO).content.decode()

    assert "Stock" in contenido
    assert _editar(producto) in contenido and _baja(producto) in contenido
    assert "Incluir dados de baja" in contenido


# Filtro de dados de baja (agregado del alumno)


def test_por_defecto_solo_se_listan_los_activos(client, admin, producto):
    producto.activo = False
    producto.save()
    client.force_login(admin)

    assert list(client.get(LISTADO).context["pagina"]) == []

    respuesta = client.get(LISTADO, {"inactivos": "1"})
    assert list(respuesta.context["pagina"]) == [producto]
    contenido = respuesta.content.decode()
    assert "Dado de baja" in contenido
    assert _baja(producto) not in contenido  # sin reactivar ni volver a dar de baja


def test_la_cajera_no_ve_el_filtro_ni_los_dados_de_baja(client, cajera_alta, producto):
    producto.activo = False
    producto.save()
    client.force_login(cajera_alta)

    respuesta = client.get(LISTADO, {"inactivos": "1"})

    assert list(respuesta.context["pagina"]) == []
    assert "Incluir dados de baja" not in respuesta.content.decode()


def test_busqueda_desde_la_pantalla(client, admin, producto):
    client.force_login(admin)

    assert list(client.get(LISTADO, {"q": "aceite"}).context["pagina"]) == [producto]
    assert list(client.get(LISTADO, {"q": "arroz"}).context["pagina"]) == []


# CP-56 y RM-02: cajera con permiso


def test_cp56_cajera_con_permiso_da_de_alta_desde_la_pantalla(client, cajera_alta):
    client.force_login(cajera_alta)

    respuesta = client.post(NUEVO, _form())

    assert respuesta.url == LISTADO
    assert Producto.objects.filter(plus_interno="700", activo=True).exists()


def test_cajera_con_permiso_no_ve_stock_editar_ni_baja(client, cajera_alta, producto):
    client.force_login(cajera_alta)

    contenido = client.get(LISTADO).content.decode()

    assert "Nuevo producto" in contenido
    assert _editar(producto) not in contenido and _baja(producto) not in contenido
    assert ">Stock<" not in contenido


def test_cajera_con_permiso_no_edita_ni_da_de_baja_por_url(client, cajera_alta, producto):
    client.force_login(cajera_alta)

    assert client.get(_editar(producto)).status_code == 403
    assert client.post(_editar(producto), _form()).status_code == 403
    assert client.post(_baja(producto)).status_code == 403
    producto.refresh_from_db()
    assert producto.activo and producto.nombre == "Aceite 1 l"


# CP-55 y CP-53: sin permiso, ni pantalla ni URL directa


@pytest.mark.parametrize("quien", ["cajera", "duenio"])
def test_cp55_cp53_sin_permiso_no_entran_a_ninguna_pantalla(client, request, producto, quien):
    client.force_login(request.getfixturevalue(quien))

    for url in (LISTADO, NUEVO, _editar(producto), _baja(producto)):
        assert client.get(url).status_code == 403, url
    assert client.post(NUEVO, _form()).status_code == 403
    assert not Producto.objects.filter(plus_interno="700").exists()


def test_sin_sesion_redirige_al_ingreso(client):
    respuesta = client.get(NUEVO)

    assert respuesta.url.startswith(reverse("usuarios:ingresar"))


def test_el_menu_de_la_cajera_sin_permiso_no_muestra_productos(client, cajera):
    client.force_login(cajera)

    assert LISTADO not in client.get(reverse("inicio")).content.decode()


# CP-59 y RI-16 desde la pantalla: mensajes junto al campo


def test_cp59_plus_repetido_muestra_el_mensaje_junto_al_campo(client, admin):
    client.force_login(admin)
    client.post(NUEVO, _form())

    respuesta = client.post(NUEVO, _form(nombre="Otro"))

    assert respuesta.status_code == 200
    assert respuesta.context["form"].errors == {
        "plus_interno": ["Ya existe un producto con el plus interno 700."]
    }
    assert Producto.objects.count() == 1


def test_precio_negativo_muestra_el_mensaje_junto_al_campo(client, admin):
    client.force_login(admin)

    respuesta = client.post(NUEVO, _form(precio_venta="-1"))

    assert respuesta.context["form"].errors == {"precio_venta": ["No puede ser negativo."]}
    assert 'min="0"' in respuesta.content.decode()


def test_el_formulario_no_tiene_stock_actual(client, admin):
    client.force_login(admin)

    client.post(NUEVO, _form(stock_actual="99"))

    assert "stock_actual" not in client.get(NUEVO).context["form"].fields
    assert Producto.objects.get(plus_interno="700").stock_actual == 0
