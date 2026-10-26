"""CU-01 A1: alta de producto durante la venta (RF-17, RN-05, DEC-62 a DEC-65)."""

import json
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.caja.models import Turno
from apps.caja.services import abrir_caja
from apps.catalogo.models import Producto, UnidadMedida
from apps.catalogo.services import crear_producto
from apps.usuarios.models import Rol, Usuario
from apps.ventas.services import registrar_venta

pytestmark = pytest.mark.django_db

NUEVA = reverse("ventas:nueva")
ALTA = reverse("ventas:producto_nuevo")


def _crear(username, rol, **extra):
    return Usuario.objects.create_user(
        username=username,
        password="clave-de-prueba-123",
        nombre_completo=username,
        rol=rol,
        **extra,
    )


@pytest.fixture
def cajera_alta(db):
    return _crear("cajera_alta", Rol.CAJERA, puede_crear_productos=True)


@pytest.fixture
def caja_hoy(usuario):
    return abrir_caja(usuario, Turno.MANANA)


def _datos(**cambios):
    datos = {
        "producto-nombre": "Matambre de cerdo",
        "producto-categoria": "",
        "producto-plus_interno": "",
        "producto-precio_venta": "8500.00",
        "producto-unidad_medida": UnidadMedida.KG,
        "producto-stock_minimo": "",
    }
    datos.update(cambios)
    return {clave: valor for clave, valor in datos.items() if valor is not None}


def test_cp56_la_cajera_con_permiso_crea_el_producto_desde_la_venta(client, cajera_alta):
    client.force_login(cajera_alta)

    respuesta = client.post(ALTA, _datos(**{"producto-plus_interno": "777"}))

    assert respuesta.status_code == 200
    producto = Producto.objects.get(nombre="Matambre de cerdo")
    assert respuesta.json() == {
        "producto": {
            "id": producto.pk,
            "nombre": "Matambre de cerdo",
            "plus": "777",
            "precio": "8500.00",
            "unidad": "KG",
        }
    }
    assert producto.stock_actual == 0
    assert producto.activo


@pytest.mark.parametrize("rol", ["cajera_sin_permiso", Rol.ADMINISTRADOR, Rol.DUENIO])
def test_cp55_sin_permiso_de_alta_desde_la_venta_da_403(client, rol):
    if rol == "cajera_sin_permiso":
        usuario = _crear("cajera_sin", Rol.CAJERA)
    else:
        usuario = _crear("otro", rol)
    client.force_login(usuario)

    assert client.post(ALTA, _datos()).status_code == 403
    assert not Producto.objects.filter(nombre="Matambre de cerdo").exists()


def test_sin_sesion_el_alta_lleva_al_ingreso(client):
    respuesta = client.post(ALTA, _datos())

    assert respuesta.status_code == 302
    assert reverse("usuarios:ingresar") in respuesta["Location"]


def test_el_alta_solo_acepta_post(client, cajera_alta):
    client.force_login(cajera_alta)

    assert client.get(ALTA).status_code == 405


def test_cu11_a1_plus_repetido_se_rechaza_junto_al_campo(client, cajera_alta, producto):
    producto.plus_interno = "501"
    producto.save()
    client.force_login(cajera_alta)

    respuesta = client.post(ALTA, _datos(**{"producto-plus_interno": "501"}))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"]["plus_interno"] == [
        "Ya existe un producto con el plus interno 501."
    ]
    assert not Producto.objects.filter(nombre="Matambre de cerdo").exists()


def test_datos_invalidos_vuelven_por_campo(client, cajera_alta):
    client.force_login(cajera_alta)

    respuesta = client.post(ALTA, _datos(**{"producto-nombre": "", "producto-unidad_medida": ""}))

    assert respuesta.status_code == 400
    errores = respuesta.json()["errores"]
    assert set(errores) == {"nombre", "unidad_medida"}
    assert Producto.objects.count() == 0


def test_dec63_la_pantalla_ofrece_el_alta_solo_con_permiso(client, cajera_alta, usuario, caja_hoy):
    client.force_login(cajera_alta)
    con_permiso = client.get(NUEVA).content.decode()
    client.force_login(usuario)
    sin_permiso = client.get(NUEVA).content.decode()

    assert f'data-producto="{ALTA}"' in con_permiso
    assert 'id="alta-producto"' in con_permiso
    assert 'name="producto-nombre"' in con_permiso
    assert "data-producto=" not in sin_permiso
    assert 'id="alta-producto"' not in sin_permiso


def test_dec46_el_producto_nuevo_con_stock_se_vende_con_aviso(
    client, cajera_alta, caja_hoy, efectivo
):
    client.force_login(cajera_alta)
    datos = _datos(
        **{
            "producto-nombre": "Fernet 750 ml",
            "producto-precio_venta": "12000.00",
            "producto-unidad_medida": UnidadMedida.UNIDAD,
            "producto-controla_stock": "on",
        }
    )
    nuevo = client.post(ALTA, datos).json()["producto"]

    respuesta = client.post(
        reverse("ventas:confirmar"),
        {
            "medio_pago": efectivo.pk,
            "lineas": json.dumps([{"producto": nuevo["id"], "cantidad": "1"}]),
        },
    )

    assert "ticket" in respuesta.json()
    producto = Producto.objects.get(pk=nuevo["id"])
    assert producto.stock_actual == Decimal("-1")


def test_rf17_el_producto_creado_se_vende_en_la_misma_venta(
    cajera_alta, caja_hoy, efectivo, producto
):
    nuevo = crear_producto(
        cajera_alta,
        {
            "nombre": "Matambre de cerdo",
            "precio_venta": Decimal("8500.00"),
            "unidad_medida": UnidadMedida.KG,
            "controla_stock": False,
        },
    )

    venta, _ = registrar_venta(
        cajera_alta, [(producto.pk, Decimal("1")), (nuevo.pk, Decimal("0.5"))], efectivo
    )

    assert venta.monto_total == Decimal("6750.00")


def test_dec46_el_alta_en_la_venta_avisa_el_stock_negativo(client, cajera_alta, caja_hoy):
    client.force_login(cajera_alta)

    contenido = client.get(NUEVA).content.decode()

    assert "Si lo marcás, el stock arranca en 0 y queda negativo con esta venta" in contenido
