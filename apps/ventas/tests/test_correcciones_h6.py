"""Etapa 1 de H6 en la venta: tope de líneas (CP-141), paginación de "Ventas de la caja"
(CP-142) y stock al retomar una venta guardada (CP-145)."""

import json
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.caja.models import MovimientoCaja, Turno
from apps.caja.services import abrir_caja
from apps.catalogo.models import Producto, UnidadMedida
from apps.catalogo.services import STOCK_MAXIMO
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import DetalleVenta, Venta
from apps.ventas.services import (
    LINEAS_MAXIMAS,
    MENSAJE_LINEAS_MAXIMAS,
    registrar_venta,
    stock_para_venta,
)

pytestmark = pytest.mark.django_db

STOCK = reverse("ventas:stock")


@pytest.fixture
def caja_hoy(usuario):
    return abrir_caja(usuario, Turno.MANANA)


@pytest.fixture
def productos(categoria):
    return Producto.objects.bulk_create(
        Producto(
            nombre=f"Producto {i}",
            categoria=categoria,
            precio_venta=Decimal("100.00"),
            unidad_medida=UnidadMedida.UNIDAD,
            controla_stock=False,
        )
        for i in range(LINEAS_MAXIMAS + 1)
    )


def _lineas(productos):
    return [(p.pk, Decimal("1")) for p in productos]


# CP-141: tope de 50 líneas (L5, DEC-162, DEC-173)


def test_cp141_con_50_lineas_la_venta_se_registra(usuario, caja_hoy, efectivo, productos):
    venta, _ = registrar_venta(usuario, _lineas(productos[:LINEAS_MAXIMAS]), efectivo)

    assert DetalleVenta.objects.filter(venta=venta).count() == LINEAS_MAXIMAS == 50


def test_cp141_con_51_lineas_se_rechaza_sin_registrar_nada(usuario, caja_hoy, efectivo, productos):
    with pytest.raises(ValidationError) as error:
        registrar_venta(usuario, _lineas(productos), efectivo)

    assert error.value.messages == [MENSAJE_LINEAS_MAXIMAS]
    assert not Venta.objects.exists()


def test_cp141_el_tope_cuenta_las_lineas_agrupadas(usuario, caja_hoy, efectivo, productos):
    # 50 productos y uno repetido: siguen siendo 50 líneas (DEC-53).
    lineas = _lineas(productos[:LINEAS_MAXIMAS]) + [(productos[0].pk, Decimal("1"))]

    venta, _ = registrar_venta(usuario, lineas, efectivo)

    assert DetalleVenta.objects.filter(venta=venta).count() == LINEAS_MAXIMAS


def test_cp141_la_pantalla_rechaza_51_lineas_con_el_mensaje(
    client, usuario, caja_hoy, efectivo, productos
):
    client.force_login(usuario)
    lineas = [{"producto": p.pk, "cantidad": "1"} for p in productos]

    respuesta = client.post(
        reverse("ventas:confirmar"), {"medio_pago": efectivo.pk, "lineas": json.dumps(lineas)}
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == [MENSAJE_LINEAS_MAXIMAS]


def test_cp141_el_formulario_recibe_el_tope_y_el_mensaje(client, usuario, caja_hoy):
    client.force_login(usuario)

    contenido = client.get(reverse("ventas:nueva")).content.decode()

    assert f'data-lineas-maximas="{LINEAS_MAXIMAS}"' in contenido
    assert "La venta llegó a 50 productos: confirmala y empezá otra." in contenido
    assert f'data-stock="{STOCK}"' in contenido


# CP-142: "Ventas de la caja" paginada de a 25 (L6, DEC-174)


def test_cp142_ventas_de_la_caja_pagina_de_a_25(client, usuario, caja_hoy, efectivo, productos):
    for _ in range(26):
        registrar_venta(usuario, _lineas(productos[:1]), efectivo)
    client.force_login(usuario)
    url = reverse("ventas:lista")

    primera = client.get(url)
    segunda = client.get(url, {"pagina": 2})

    assert len(primera.context["pagina"].object_list) == 25
    ultima = Venta.objects.order_by("-fecha_hora", "-pk").first()
    assert primera.context["pagina"].object_list[0] == ultima
    assert "Página 1 de 2" in primera.content.decode()
    assert 'href="?pagina=2"' in primera.content.decode()
    assert len(segunda.context["pagina"].object_list) == 1


def test_cp142_sin_caja_abierta_avisa_sin_listar(client, usuario):
    client.force_login(usuario)

    respuesta = client.get(reverse("ventas:lista"))

    assert respuesta.status_code == 200
    assert "No hay una caja abierta" in respuesta.content.decode()


# CP-145: stock actual al retomar una venta guardada (L11, DEC-165, DEC-176)


@pytest.fixture
def aceite(producto):
    producto.stock_actual = Decimal("3")
    producto.save()
    return producto


def test_cp145_el_servicio_devuelve_el_stock_actual(aceite, productos):
    sin_control = productos[0]

    assert stock_para_venta([aceite.pk, sin_control.pk, 999999]) == {
        aceite.pk: Decimal("3.000"),
        sin_control.pk: None,  # sin control de stock, sin aviso (DEC-36)
    }


def test_cp145_la_cajera_consulta_el_stock_de_la_venta_guardada(client, usuario, aceite, productos):
    client.force_login(usuario)

    respuesta = client.get(STOCK, {"ids": f"{aceite.pk},{productos[0].pk}"})

    assert respuesta.json() == {"stock": {str(aceite.pk): "3.000", str(productos[0].pk): None}}


def test_cp145_ids_invalidos_o_de_mas_se_rechazan(client, usuario, aceite):
    client.force_login(usuario)
    de_mas = ",".join(str(i) for i in range(1, LINEAS_MAXIMAS + 2))

    assert client.get(STOCK, {"ids": "1,x"}).status_code == 400
    assert client.get(STOCK, {"ids": str(2**63)}).status_code == 400
    assert client.get(STOCK, {"ids": "0"}).status_code == 400
    assert client.get(STOCK, {"ids": de_mas}).status_code == 400
    assert client.get(STOCK).json() == {"stock": {}}


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_cp145_solo_la_cajera_consulta_el_stock(client, rol, aceite):
    otro = Usuario.objects.create_user(
        username="otro", password="clave-de-prueba-123", nombre_completo="Otro", rol=rol
    )
    client.force_login(otro)

    assert client.get(STOCK, {"ids": str(aceite.pk)}).status_code == 403


def test_cp145_solo_por_get(client, usuario):
    client.force_login(usuario)

    assert client.post(STOCK).status_code == 405


# CP-143 en la venta: el rechazo del stock deshace toda la venta (L19, DEC-175)


def test_cp143_una_venta_que_deja_el_stock_fuera_de_rango_no_registra_nada(
    usuario, caja_hoy, efectivo, aceite
):
    aceite.stock_actual = -STOCK_MAXIMO
    aceite.save()

    with pytest.raises(ValidationError) as error:
        registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)

    assert "quedaría fuera del rango permitido" in error.value.messages[0]
    assert not Venta.objects.exists() and not MovimientoCaja.objects.exists()
    aceite.refresh_from_db()
    assert aceite.stock_actual == -STOCK_MAXIMO
