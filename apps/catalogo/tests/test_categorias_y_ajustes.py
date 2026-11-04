"""CP-135 y CP-136: categorías y consulta de ajustes de stock fuera del panel (DEC-155, L18)."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.catalogo.forms import ProductoForm
from apps.catalogo.models import AjusteStock, Categoria, MotivoAjuste, Producto, UnidadMedida
from apps.catalogo.services import crear_producto, modificar_producto

pytestmark = pytest.mark.django_db


def _datos_producto(categoria, **cambios):
    datos = {
        "nombre": "Yerba 1 kg",
        "categoria": categoria,
        "plus_interno": None,
        "precio_venta": Decimal("3000.00"),
        "unidad_medida": UnidadMedida.UNIDAD,
        "controla_stock": False,
        "stock_minimo": None,
    }
    datos.update(cambios)
    return datos


# CP-135: categorías


def test_cp135_alta_edicion_y_nombre_repetido_sin_mayusculas(client, admin, categoria):
    client.force_login(admin)

    assert (
        client.post(reverse("catalogo:categoria_nueva"), {"nombre": " Lácteos "}).status_code == 302
    )
    lacteos = Categoria.objects.get(nombre="Lácteos")
    respuesta = client.post(reverse("catalogo:categoria_nueva"), {"nombre": "ALMACÉN"})
    assert respuesta.status_code == 200
    assert "Ya existe una categoría con ese nombre." in respuesta.content.decode()

    client.post(
        reverse("catalogo:categoria_editar", args=[lacteos.pk]), {"nombre": "Lácteos y quesos"}
    )
    lacteos.refresh_from_db()
    assert lacteos.nombre == "Lácteos y quesos"
    assert Categoria.objects.count() == 2


def test_cp135_baja_logica_los_productos_la_conservan_y_no_se_ofrece(client, admin, producto):
    categoria = producto.categoria
    client.force_login(admin)

    confirmacion = client.get(reverse("catalogo:categoria_baja", args=[categoria.pk]))
    assert "El producto que la tiene la conserva." in confirmacion.content.decode()
    client.post(reverse("catalogo:categoria_baja", args=[categoria.pk]))

    categoria.refresh_from_db()
    producto.refresh_from_db()
    assert not categoria.activo
    assert producto.categoria == categoria
    # No se ofrece para un producto nuevo, pero sí al editar el que ya la tiene.
    assert categoria not in ProductoForm().fields["categoria"].queryset
    assert (
        categoria in ProductoForm(initial={"categoria": categoria.pk}).fields["categoria"].queryset
    )
    # El listado de activas no la muestra; con "Incluir dadas de baja", sí.
    assert categoria not in client.get(reverse("catalogo:categorias")).context["categorias"]
    con_bajas = client.get(reverse("catalogo:categorias") + "?inactivas=1").context["categorias"]
    assert categoria in con_bajas


def test_cp135_el_servicio_no_asigna_una_categoria_dada_de_baja(admin, producto, categoria):
    otra = Categoria.objects.create(nombre="Bebidas", activo=False)

    with pytest.raises(ValidationError, match="dada de baja"):
        crear_producto(admin, _datos_producto(otra))
    with pytest.raises(ValidationError, match="dada de baja"):
        modificar_producto(admin, producto, _datos_producto(otra, nombre=producto.nombre))

    # El producto que ya la tiene se sigue modificando sin cambiarla.
    categoria.activo = False
    categoria.save()
    modificar_producto(admin, producto, _datos_producto(categoria, nombre="Aceite 900 ml"))
    producto.refresh_from_db()
    assert producto.nombre == "Aceite 900 ml"
    assert producto.categoria == categoria


def test_cp135_reactivar_una_categoria(client, admin):
    categoria = Categoria.objects.create(nombre="Bebidas", activo=False)
    client.force_login(admin)

    assert client.get(reverse("catalogo:categoria_editar", args=[categoria.pk])).status_code == 404
    client.post(reverse("catalogo:categoria_reactivar", args=[categoria.pk]))

    categoria.refresh_from_db()
    assert categoria.activo


# CP-136: consulta de ajustes de stock


def _ajuste(producto, usuario, dias_atras, nuevo):
    return AjusteStock.objects.create(
        producto=producto,
        usuario=usuario,
        fecha_hora=timezone.now() - datetime.timedelta(days=dias_atras),
        stock_anterior=Decimal("0"),
        stock_nuevo=Decimal(nuevo),
        motivo=MotivoAjuste.MODIFICACION_MANUAL,
    )


def test_cp136_lista_los_ajustes_mas_nuevos_primero_y_filtra(client, admin, producto, categoria):
    otro = Producto.objects.create(
        nombre="Fideos",
        categoria=categoria,
        precio_venta=Decimal("900.00"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=True,
    )
    viejo = _ajuste(producto, admin, 10, "5")
    nuevo = _ajuste(producto, admin, 0, "8")
    de_otro = _ajuste(otro, admin, 1, "3")
    client.force_login(admin)
    url = reverse("catalogo:ajustes")

    assert list(client.get(url).context["pagina"].object_list) == [nuevo, de_otro, viejo]
    por_producto = client.get(url, {"producto": producto.pk}).context["pagina"].object_list
    assert list(por_producto) == [nuevo, viejo]
    hace_dos = (timezone.localdate() - datetime.timedelta(days=2)).isoformat()
    recientes = client.get(url, {"desde": hace_dos}).context["pagina"].object_list
    assert list(recientes) == [nuevo, de_otro]


@pytest.mark.parametrize(
    "filtro",
    [
        {"desde": "2026-03-10", "hasta": "2026-03-01"},
        {"hasta": (timezone.localdate() + datetime.timedelta(days=1)).isoformat()},
    ],
)
def test_cp136_un_rango_invalido_muestra_el_error_y_no_lista(client, admin, producto, filtro):
    _ajuste(producto, admin, 0, "5")
    client.force_login(admin)

    respuesta = client.get(reverse("catalogo:ajustes"), filtro)

    assert respuesta.context["form"].errors
    assert not respuesta.context["pagina"].object_list


def test_cp136_los_ajustes_son_de_solo_lectura(client, admin):
    client.force_login(admin)

    assert client.post(reverse("catalogo:ajustes")).status_code == 405


# DEC-155: solo el Administrador; la cajera ve Productos pero no estas pestañas


@pytest.mark.parametrize(
    "url",
    ["catalogo:categorias", "catalogo:categoria_nueva", "catalogo:ajustes"],
)
def test_dec155_la_cajera_no_gestiona_categorias_ni_ve_ajustes(client, cajera_alta, url):
    client.force_login(cajera_alta)

    assert client.get(reverse(url)).status_code == 403
    productos = client.get(reverse("catalogo:productos")).content.decode()
    assert reverse("catalogo:categorias") not in productos


def test_dec155_el_administrador_ve_las_pestanas_en_productos(client, admin):
    client.force_login(admin)

    contenido = client.get(reverse("catalogo:productos")).content.decode()

    assert reverse("catalogo:categorias") in contenido
    assert reverse("catalogo:ajustes") in contenido
