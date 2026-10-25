"""CU-01 de punta a punta: pantalla de venta, búsqueda, confirmación y ticket."""

import json
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.caja.models import MedioPago, MovimientoCaja, Turno
from apps.caja.services import abrir_caja
from apps.catalogo.models import Producto, UnidadMedida
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import Venta

pytestmark = pytest.mark.django_db

NUEVA = reverse("ventas:nueva")
BUSCAR = reverse("ventas:buscar")
CONFIRMAR = reverse("ventas:confirmar")


@pytest.fixture
def caja_hoy(usuario):
    return abrir_caja(usuario, Turno.MANANA)


@pytest.fixture
def aceite(producto):
    producto.plus_interno = "501"
    producto.stock_actual = Decimal("10")
    producto.save()
    return producto


@pytest.fixture
def asado(categoria):
    return Producto.objects.create(
        nombre="Asado",
        categoria=categoria,
        plus_interno="101",
        precio_venta=Decimal("9800.00"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=False,
    )


def _confirmar(client, medio, lineas):
    return client.post(
        CONFIRMAR, {"medio_pago": medio.pk if medio else "", "lineas": json.dumps(lineas)}
    )


# Pantalla y caja (CU-01 A4, DEC-50, DEC-51)


def test_la_pantalla_ofrece_los_medios_sin_valor_por_defecto(client, usuario, caja_hoy, efectivo):
    MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)
    client.force_login(usuario)

    respuesta = client.get(NUEVA)

    opciones = list(respuesta.context["form"].fields["medio_pago"].choices)
    assert [str(etiqueta) for _, etiqueta in opciones] == ["Elegí un medio de pago", "Efectivo"]
    assert respuesta.context["problema"] is None
    assert 'id="buscar"' in respuesta.content.decode()


def test_cp17_sin_caja_abierta_avisa_y_enlaza_a_caja(client, usuario):
    client.force_login(usuario)

    contenido = client.get(NUEVA).content.decode()

    assert "No hay una caja abierta. Abrí la caja para vender." in contenido
    assert f'href="{reverse("caja:caja")}"' in contenido
    assert 'id="buscar"' not in contenido


def test_dec50_con_la_caja_de_otro_dia_avisa(client, usuario, caja):
    client.force_login(usuario)

    assert "La caja abierta es de otro día." in client.get(NUEVA).content.decode()


# Búsqueda (CP-82)


def test_cp82_la_busqueda_devuelve_el_exacto_y_los_resultados(client, usuario, aceite, asado):
    client.force_login(usuario)

    datos = client.get(BUSCAR, {"q": "101"}).json()
    assert datos["exacto"] == {
        "id": asado.pk,
        "nombre": "Asado",
        "plus": "101",
        "precio": "9800.00",
        "unidad": "KG",
    }

    datos = client.get(BUSCAR, {"q": "acei"}).json()
    assert datos["exacto"] is None
    assert [p["id"] for p in datos["resultados"]] == [aceite.pk]
    assert "stock" not in datos["resultados"][0]


# Confirmación y ticket (CP-10, CP-11, CP-84, DEC-47, DEC-54)


def test_venta_completa_desde_la_pantalla_y_ticket(
    client, usuario, caja_hoy, efectivo, aceite, asado
):
    client.force_login(usuario)

    respuesta = _confirmar(
        client,
        efectivo,
        [{"producto": aceite.pk, "cantidad": "2"}, {"producto": asado.pk, "cantidad": "1.250"}],
    )

    venta = Venta.objects.get()
    assert respuesta.json() == {"ticket": reverse("ventas:ticket", args=[venta.pk])}
    assert venta.monto_total == Decimal("17250.00")
    assert MovimientoCaja.objects.get().monto == Decimal("17250.00")

    contenido = client.get(respuesta.json()["ticket"]).content.decode()
    for texto in [
        "Carnicería Rojano",
        f"Venta N.º {venta.pk}",
        "Atendió: Cajera Uno",
        "Aceite 1 l",
        "1,250 kg",
        "$ 17.250,00",
        "Medio de pago: Efectivo",
        "No válido como factura",
        "Imprimir",
        "Nueva venta",
    ]:
        assert texto in contenido, texto


def test_dec47_los_precios_del_navegador_se_ignoran(client, usuario, caja_hoy, efectivo, aceite):
    client.force_login(usuario)

    _confirmar(
        client,
        efectivo,
        [{"producto": aceite.pk, "cantidad": "1", "precio": "1.00", "subtotal": "1.00"}],
    )

    venta = Venta.objects.get()
    assert venta.monto_total == Decimal("2500.00")
    assert venta.detalleventa_set.get().precio_unitario == Decimal("2500.00")


def test_cp83_el_aviso_de_stock_se_ve_en_el_ticket(client, usuario, caja_hoy, efectivo, aceite):
    client.force_login(usuario)

    respuesta = _confirmar(client, efectivo, [{"producto": aceite.pk, "cantidad": "12"}])

    contenido = client.get(respuesta.json()["ticket"]).content.decode()
    assert "Stock insuficiente de Aceite 1 l" in contenido


# Errores (CP-16, CP-17, DEC-51)


def test_sin_medio_de_pago_se_rechaza(client, usuario, caja_hoy, aceite):
    client.force_login(usuario)

    respuesta = _confirmar(client, None, [{"producto": aceite.pk, "cantidad": "1"}])

    assert respuesta.status_code == 400
    assert respuesta.json() == {"errores": ["Elegí un medio de pago."]}
    assert not Venta.objects.exists()


def test_lista_invalida_o_vacia_se_rechaza(client, usuario, caja_hoy, efectivo):
    client.force_login(usuario)

    respuesta = client.post(CONFIRMAR, {"medio_pago": efectivo.pk, "lineas": "no es json"})
    assert respuesta.json() == {"errores": ["La lista de productos no es válida."]}

    respuesta = _confirmar(client, efectivo, [{"producto": 1, "cantidad": "NaN"}])
    assert respuesta.json() == {"errores": ["La lista de productos no es válida."]}

    respuesta = _confirmar(client, efectivo, [])
    assert respuesta.json() == {"errores": ["La venta no tiene productos."]}
    assert not Venta.objects.exists()


def test_cp16_cantidad_cero_se_rechaza_con_mensaje(client, usuario, caja_hoy, efectivo, aceite):
    client.force_login(usuario)

    respuesta = _confirmar(client, efectivo, [{"producto": aceite.pk, "cantidad": "0"}])

    assert respuesta.status_code == 400
    assert respuesta.json() == {"errores": ["La cantidad de Aceite 1 l tiene que ser mayor a 0."]}


def test_cp17_confirmar_sin_caja_abierta_se_rechaza(client, usuario, efectivo, aceite):
    client.force_login(usuario)

    respuesta = _confirmar(client, efectivo, [{"producto": aceite.pk, "cantidad": "1"}])

    assert respuesta.json() == {"errores": ["No hay una caja abierta. Abrí la caja para vender."]}


def test_confirmar_solo_por_post(client, usuario):
    client.force_login(usuario)

    assert client.get(CONFIRMAR).status_code == 405


# Permisos (RF-02, RNF-06)


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_administrador_y_duenios_no_acceden(client, rol, caja_hoy, efectivo, aceite):
    otro = Usuario.objects.create_user(
        username="otro", password="clave-de-prueba-123", nombre_completo="Otro", rol=rol
    )
    client.force_login(otro)

    assert client.get(NUEVA).status_code == 403
    assert client.get(BUSCAR, {"q": "a"}).status_code == 403
    assert (
        _confirmar(client, efectivo, [{"producto": aceite.pk, "cantidad": "1"}]).status_code == 403
    )
    assert not Venta.objects.exists()


def test_sin_sesion_redirige_al_ingreso(client):
    respuesta = client.get(NUEVA)

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(reverse("usuarios:ingresar"))


def test_el_menu_de_la_cajera_enlaza_ventas(client, usuario):
    client.force_login(usuario)

    assert f'href="{NUEVA}"' in client.get(reverse("inicio")).content.decode()
