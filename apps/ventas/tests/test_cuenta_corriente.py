"""SC-03 Vender a cuenta corriente y L1 (H4, etapa 3).

CP-18, CP-19, CP-115 y CP-116; DEC-108, DEC-109, DEC-113, DEC-114, DEC-116; S-3 a S-5 y S-11
(DEC-122 a DEC-124, DEC-130); R-2 y R-6.
"""

import json
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import EstadoCaja, MedioPago, MovimientoCaja, Turno
from apps.caja.services import abrir_caja, cerrar_caja, medios_del_cierre, resumen_de_cierre
from apps.clientes.models import (
    Cliente,
    MovimientoCuentaCorriente,
    PagoCliente,
    TipoMovimientoCuentaCorriente,
)
from apps.clientes.services import saldo
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import EstadoVenta, Venta
from apps.ventas.services import (
    anular_venta,
    historial_de_ventas,
    registrar_venta,
    resumen_del_dia,
)

pytestmark = pytest.mark.django_db

Tipo = TipoMovimientoCuentaCorriente
NUEVA = reverse("ventas:nueva")
CONFIRMAR = reverse("ventas:confirmar")


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        username="admin",
        password="clave-de-prueba-123",
        nombre_completo="Admin",
        rol=Rol.ADMINISTRADOR,
    )


@pytest.fixture
def caja_hoy(usuario, efectivo):
    return abrir_caja(usuario, Turno.MANANA, Decimal("5000.00"))


@pytest.fixture
def cuenta_corriente(db):
    return MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)


@pytest.fixture
def aceite(producto):
    # $ 2.500 por unidad, con stock.
    producto.stock_actual = Decimal("10")
    producto.save()
    return producto


def _vender(usuario, aceite, medio, cliente=None, unidades="1"):
    venta, _ = registrar_venta(usuario, [(aceite.pk, Decimal(unidades))], medio, cliente)
    return venta


def _cobro(cliente, usuario, efectivo, monto):
    """Un cobro como lo dejará CU-04 (etapa 4): baja el saldo."""
    pago = PagoCliente.objects.create(
        cliente=cliente, monto=Decimal(monto), medio_pago=efectivo, usuario=usuario
    )
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente, tipo=Tipo.PAGO, monto=Decimal(monto), pago_cliente=pago
    )


# CP-18 y CP-19 (RI-05, R-2)


def test_cp18_venta_a_cuenta_corriente_deja_la_deuda_sin_caja(
    usuario, caja_hoy, cuenta_corriente, cliente, aceite
):
    venta = _vender(usuario, aceite, cuenta_corriente, cliente, unidades="2")

    assert venta.cliente == cliente and venta.monto_total == Decimal("5000.00")
    cargo = MovimientoCuentaCorriente.objects.get()
    assert (cargo.tipo, cargo.monto, cargo.venta, cargo.cliente) == (
        Tipo.VENTA_FIADA,
        Decimal("5000.00"),
        venta,
        cliente,
    )
    assert not MovimientoCaja.objects.exists()
    assert saldo(cliente) == Decimal("5000.00")
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("8")


def test_cp19_venta_a_cuenta_corriente_sin_cliente_se_rechaza(
    usuario, caja_hoy, cuenta_corriente, aceite
):
    with pytest.raises(ValidationError) as error:
        _vender(usuario, aceite, cuenta_corriente)

    assert error.value.message_dict == {"cliente": ["Elegí el cliente de la cuenta corriente."]}
    assert not Venta.objects.exists() and not MovimientoCuentaCorriente.objects.exists()


def test_con_otro_medio_el_cliente_no_se_usa(usuario, caja_hoy, efectivo, cliente, aceite):
    venta = _vender(usuario, aceite, efectivo, cliente)

    assert venta.cliente is None
    assert not MovimientoCuentaCorriente.objects.exists()
    assert MovimientoCaja.objects.filter(venta=venta).count() == 1


def test_dec116_un_cliente_dado_de_baja_no_compra_a_cuenta_corriente(
    usuario, caja_hoy, cuenta_corriente, cliente, aceite
):
    cliente.activo = False
    cliente.save()

    with pytest.raises(ValidationError) as error:
        _vender(usuario, aceite, cuenta_corriente, cliente)

    assert error.value.code == "cliente_inactivo"
    assert not Venta.objects.exists()


# CP-115: límite de crédito (DEC-108, DEC-115)


def test_cp115_llegar_al_limite_se_acepta_y_pasarlo_se_rechaza_sin_guardar_nada(
    usuario, caja_hoy, cuenta_corriente, cliente, aceite
):
    cliente.limite_credito = Decimal("5000")
    cliente.save()
    _vender(usuario, aceite, cuenta_corriente, cliente, unidades="2")  # saldo 5.000

    with pytest.raises(ValidationError) as error:
        _vender(usuario, aceite, cuenta_corriente, cliente)

    assert error.value.code == "limite_superado"
    assert "disponible $ 0,00" in error.value.messages[0]
    assert Venta.objects.count() == 1 and saldo(cliente) == Decimal("5000.00")
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("8")


def test_cp115_sin_limite_no_hay_tope(usuario, caja_hoy, cuenta_corriente, cliente, aceite):
    _vender(usuario, aceite, cuenta_corriente, cliente, unidades="40")

    assert saldo(cliente) == Decimal("100000.00")


def test_cp115_con_limite_cero_no_hay_credito(usuario, caja_hoy, cuenta_corriente, cliente, aceite):
    cliente.limite_credito = Decimal("0")
    cliente.save()

    with pytest.raises(ValidationError) as error:
        _vender(usuario, aceite, cuenta_corriente, cliente)

    assert error.value.code == "sin_credito"
    assert not Venta.objects.exists()


# S-5 (DEC-124): ticket, cierre, resumen del día e historial


def test_s5_el_cierre_no_cuenta_la_venta_a_cuenta_corriente(
    usuario, caja_hoy, efectivo, cuenta_corriente, cliente, aceite
):
    _vender(usuario, aceite, cuenta_corriente, cliente)
    _vender(usuario, aceite, efectivo)

    assert cuenta_corriente not in medios_del_cierre(caja_hoy)
    assert resumen_de_cierre(caja_hoy) == [(efectivo, Decimal("7500.00"))]
    cerrar_caja(usuario, {efectivo.pk: Decimal("7500.00")})
    caja_hoy.refresh_from_db()
    assert caja_hoy.estado == EstadoCaja.CERRADA and caja_hoy.observacion_cierre == ""


def test_s5_el_resumen_del_dia_y_el_historial_la_cuentan(
    usuario, caja_hoy, efectivo, cuenta_corriente, cliente, aceite
):
    a_cuenta = _vender(usuario, aceite, cuenta_corriente, cliente)
    contado = _vender(usuario, aceite, efectivo)

    # La fecha local de la venta, no la de UTC: entre las 21 y las 24 son distintas (RM-13).
    assert resumen_del_dia(timezone.localdate(a_cuenta.fecha_hora)) == (2, Decimal("5000.00"))
    ventas, _ = historial_de_ventas()
    assert set(ventas) == {a_cuenta, contado}


def test_s5_el_ticket_muestra_el_cliente_sin_su_saldo(
    client, usuario, caja_hoy, cuenta_corriente, cliente, aceite
):
    venta = _vender(usuario, aceite, cuenta_corriente, cliente)
    client.force_login(usuario)

    html = client.get(reverse("ventas:ticket", args=[venta.pk])).content.decode()

    assert "Cliente: Cliente de prueba" in html
    assert "Medio de pago: Cuenta corriente" in html
    assert "Saldo" not in html


# Pantalla de la venta (S-3, S-4)


def test_s3_la_pantalla_ofrece_cuenta_corriente_con_sc01(
    client, usuario, caja_hoy, efectivo, cuenta_corriente
):
    client.force_login(usuario)

    html = client.get(NUEVA).content.decode()

    assert f'data-cuenta-corriente="{cuenta_corriente.pk}"' in html
    assert f'data-clientes="{reverse("clientes:buscar")}"' in html
    assert 'id="buscar-cliente"' in html


def test_s3_sin_medio_cuenta_corriente_no_hay_eleccion_de_cliente(
    client, usuario, caja_hoy, efectivo
):
    client.force_login(usuario)

    html = client.get(NUEVA).content.decode()

    assert "data-cuenta-corriente" not in html and 'id="buscar-cliente"' not in html


def _confirmar(client, aceite, medio, cliente=""):
    return client.post(
        CONFIRMAR,
        {
            "medio_pago": medio.pk,
            "lineas": json.dumps([{"producto": aceite.pk, "cantidad": "1"}]),
            "cliente": cliente,
        },
    )


def test_s4_la_cajera_confirma_la_venta_a_cuenta_corriente(
    client, usuario, caja_hoy, cuenta_corriente, cliente, aceite
):
    client.force_login(usuario)

    respuesta = _confirmar(client, aceite, cuenta_corriente, cliente.pk)

    venta = Venta.objects.get()
    assert respuesta.json() == {"ticket": reverse("ventas:ticket", args=[venta.pk])}
    assert venta.cliente == cliente


def test_s4_el_servidor_vuelve_a_validar_cliente_y_limite(
    client, usuario, caja_hoy, cuenta_corriente, cliente, aceite
):
    cliente.limite_credito = Decimal("100")
    cliente.save()
    client.force_login(usuario)

    sin_cliente = _confirmar(client, aceite, cuenta_corriente)
    otro_id = _confirmar(client, aceite, cuenta_corriente, 999999)
    sobre_el_limite = _confirmar(client, aceite, cuenta_corriente, cliente.pk)

    assert sin_cliente.status_code == 400
    assert sin_cliente.json()["errores"] == ["Elegí el cliente de la cuenta corriente."]
    assert otro_id.json()["errores"] == ["El cliente elegido ya no existe."]
    assert "supera el límite" in sobre_el_limite.json()["errores"][0]
    assert not Venta.objects.exists()


# CP-116 y L1: anulación con ANULACION_VENTA (DEC-113, DEC-114, S-11)


def test_cp116_anular_revierte_la_deuda_sin_egreso_de_caja(
    admin, usuario, caja_hoy, cuenta_corriente, cliente, aceite
):
    venta = _vender(usuario, aceite, cuenta_corriente, cliente, unidades="2")

    anular_venta(admin, venta, "Se cargó al cliente equivocado")

    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.ANULADA
    reversa = MovimientoCuentaCorriente.objects.get(tipo=Tipo.ANULACION_VENTA)
    assert (reversa.venta, reversa.monto, reversa.cliente) == (venta, Decimal("5000.00"), cliente)
    assert not MovimientoCaja.objects.exists()
    assert saldo(cliente) == Decimal("0.00")
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("10")


def test_cp116_dec114_con_saldo_menor_al_total_se_rechaza(
    admin, usuario, caja_hoy, efectivo, cuenta_corriente, cliente, aceite
):
    venta = _vender(usuario, aceite, cuenta_corriente, cliente, unidades="2")  # 5.000
    _cobro(cliente, usuario, efectivo, "3000")  # saldo 2.000

    with pytest.raises(ValidationError) as error:
        anular_venta(admin, venta, "Error")

    assert error.value.code == "saldo_insuficiente"
    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.CONFIRMADA
    assert saldo(cliente) == Decimal("2000.00")
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("8")


def test_dec114_los_cobros_no_quedan_atados_a_una_venta(
    admin, usuario, caja_hoy, efectivo, cuenta_corriente, cliente, aceite
):
    vieja = _vender(usuario, aceite, cuenta_corriente, cliente)  # 2.500
    _vender(usuario, aceite, cuenta_corriente, cliente)  # 2.500
    _cobro(cliente, usuario, efectivo, "2500")  # saldo 2.500, "cubre" la más vieja

    anular_venta(admin, vieja, "Error")

    assert saldo(cliente) == Decimal("0.00")


def test_cp116_la_anulacion_rechazada_se_ve_en_el_detalle(
    client, admin, usuario, caja_hoy, efectivo, cuenta_corriente, cliente, aceite
):
    venta = _vender(usuario, aceite, cuenta_corriente, cliente, unidades="2")
    _cobro(cliente, usuario, efectivo, "3000")
    client.force_login(admin)

    detalle = client.get(reverse("ventas:detalle", args=[venta.pk])).content.decode()
    respuesta = client.post(reverse("ventas:anular", args=[venta.pk]), {"motivo": "Error"})

    assert "se descuenta de la cuenta corriente de Cliente de prueba" in detalle
    assert respuesta.status_code == 400
    assert "menor al monto de la venta" in respuesta.content.decode()
    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.CONFIRMADA


def test_l1_con_la_caja_cerrada_no_se_anula(
    admin, usuario, caja_hoy, efectivo, cuenta_corriente, cliente, aceite
):
    venta = _vender(usuario, aceite, cuenta_corriente, cliente)
    cerrar_caja(usuario, {efectivo.pk: Decimal("5000.00")})

    with pytest.raises(ValidationError) as error:
        anular_venta(admin, venta, "Error")

    assert error.value.code == "caja_cerrada"
    assert saldo(cliente) == Decimal("2500.00")


def test_s4_la_venta_elige_al_cliente_activo_de_la_busqueda(client, usuario, cliente):
    Cliente.objects.create(nombre="Cliente dado de baja", activo=False)
    client.force_login(usuario)

    datos = client.get(reverse("clientes:buscar"), {"q": "cliente"}).json()

    assert [r["nombre"] for r in datos["resultados"]] == ["Cliente de prueba"]
