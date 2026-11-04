"""CU-08 Gestionar cuentas corrientes: estado de cuenta (H4, etapa 5).

CP-44 en pantalla, CP-121 y CP-122 (criterio 12 del spec); RF-39 a RF-41; DEC-109, DEC-112,
DEC-115, DEC-119; S-10 y S-11 (DEC-129, DEC-130).
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, MovimientoCuentaCorriente, TipoMovimientoCuentaCorriente
from apps.clientes.services import (
    anular_cobro,
    movimientos_de_cuenta,
    registrar_cobro,
    saldo,
    saldo_inicial_vigente,
)
from apps.ventas.models import EstadoVenta, Venta

pytestmark = pytest.mark.django_db

Tipo = TipoMovimientoCuentaCorriente


def _estado(cliente):
    return reverse("clientes:estado", args=[cliente.pk])


def _cargar(client, cliente, monto="2000", dias_atras=45, motivo="Libreta del mostrador"):
    fecha = timezone.localdate() - datetime.timedelta(days=dias_atras)
    return client.post(
        reverse("clientes:saldo_inicial", args=[cliente.pk]),
        {"monto": monto, "fecha_origen": fecha.isoformat(), "motivo": motivo},
    )


def _anular_saldo(client, cliente, motivo="Monto mal cargado"):
    return client.post(
        reverse("clientes:saldo_inicial_anular", args=[cliente.pk]), {"motivo": motivo}
    )


def _venta_a_cuenta(cliente, caja, usuario, efectivo, monto="500", anulada=False):
    """Una venta a cuenta corriente como la deja SC-03 (etapa 3)."""
    venta = Venta.objects.create(
        caja=caja, usuario=usuario, medio_pago=efectivo, cliente=cliente, monto_total=Decimal(monto)
    )
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente, tipo=Tipo.VENTA_FIADA, monto=venta.monto_total, venta=venta
    )
    if anulada:
        venta.estado = EstadoVenta.ANULADA
        venta.anulada_en = timezone.now()
        venta.anulada_por_usuario = usuario
        venta.motivo_anulacion = "Error"
        venta.save()
        MovimientoCuentaCorriente.objects.create(
            cliente=cliente, tipo=Tipo.ANULACION_VENTA, monto=venta.monto_total, venta=venta
        )
    return venta


# S-10: solo el Administrador


@pytest.mark.parametrize("quien", ["cajera", "cajera_alta", "duenio"])
def test_s10_el_estado_de_cuenta_es_solo_del_administrador(client, request, cliente, quien):
    client.force_login(request.getfixturevalue(quien))

    assert client.get(_estado(cliente)).status_code == 403
    assert _cargar(client, cliente).status_code == 403
    assert _anular_saldo(client, cliente).status_code == 403
    respuesta = client.post(
        reverse("clientes:condiciones", args=[cliente.pk]), {"limite_credito": "0"}
    )
    assert respuesta.status_code == 403
    assert not MovimientoCuentaCorriente.objects.exists()
    with pytest.raises(PermissionDenied):
        movimientos_de_cuenta(request.getfixturevalue(quien), cliente)


def test_el_listado_enlaza_el_estado_de_cuenta(client, admin, cliente):
    client.force_login(admin)

    assert f'href="{_estado(cliente)}"' in client.get(reverse("clientes:clientes")).content.decode()


def test_un_cliente_que_no_existe_da_404(client, admin):
    client.force_login(admin)

    assert client.get(reverse("clientes:estado", args=[999999])).status_code == 404


# CP-121: saldo, límite, disponible y movimientos con sus anulaciones (RF-39)


def test_cp121_cliente_sin_movimientos(client, admin, cliente):
    client.force_login(admin)

    html = client.get(_estado(cliente)).content.decode()

    assert "Todavía no tiene movimientos" in html
    assert "Sin límite" in html and "Tiene deuda vencida" not in html


def test_cp121_muestra_saldo_limite_disponible_y_movimientos_con_enlaces(
    client, admin, cliente, caja, usuario, efectivo
):
    cliente.limite_credito = Decimal("5000")
    cliente.save()
    venta = _venta_a_cuenta(cliente, caja, usuario, efectivo, "1200")
    anulada = _venta_a_cuenta(cliente, caja, usuario, efectivo, "300", anulada=True)
    cobro = registrar_cobro(admin, cliente, Decimal("200"), efectivo, entra_a_caja=False)
    anulado = registrar_cobro(admin, cliente, Decimal("100"), efectivo, entra_a_caja=False)
    anular_cobro(admin, anulado, "Se cargó dos veces")
    client.force_login(admin)

    respuesta = client.get(_estado(cliente))
    html = respuesta.content.decode()

    assert respuesta.context["cliente"].saldo == Decimal("1000.00")
    assert "$ 1.000,00" in html and "$ 5.000,00" in html and "$ 4.000,00" in html
    assert f'href="{reverse("ventas:detalle", args=[venta.pk])}"' in html
    assert "Anulación de la <a" in html and f"venta N.º {anulada.pk}" in html
    assert f'href="{reverse("clientes:cobro", args=[cobro.pk])}"' in html
    assert f"cobro N.º {anulado.pk}" in html
    marcas = {
        (m.tipo, m.anulado)
        for m in respuesta.context["pagina"]
        if m.tipo in (Tipo.VENTA_FIADA, Tipo.PAGO)
    }
    assert marcas == {
        (Tipo.VENTA_FIADA, False),
        (Tipo.VENTA_FIADA, True),
        (Tipo.PAGO, False),
        (Tipo.PAGO, True),
    }


def test_s11_el_cobro_vigente_se_anula_desde_su_detalle(client, admin, cliente, efectivo):
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        tipo=Tipo.SALDO_INICIAL,
        monto=Decimal("500"),
        fecha_origen=timezone.localdate(),
        motivo="Deuda",
    )
    cobro = registrar_cobro(admin, cliente, Decimal("200"), efectivo, entra_a_caja=False)
    client.force_login(admin)

    html = client.get(_estado(cliente)).content.decode()
    detalle = client.get(reverse("clientes:cobro", args=[cobro.pk])).content.decode()

    assert f"{reverse('clientes:cobro', args=[cobro.pk])}#titulo-anular" in html
    assert f'href="{_estado(cliente)}"' in detalle


def test_dec115_limite_cero_y_saldo_por_encima_del_limite(client, admin, cliente):
    cliente.limite_credito = Decimal("0")
    cliente.save()
    client.force_login(admin)

    html = client.get(_estado(cliente)).content.decode()

    assert "Sin crédito habilitado" in html


def test_los_movimientos_se_paginan_de_a_25(client, admin, cliente, caja, usuario, efectivo):
    for _ in range(27):
        _venta_a_cuenta(cliente, caja, usuario, efectivo, "10")
    client.force_login(admin)

    primera = client.get(_estado(cliente))
    segunda = client.get(_estado(cliente), {"pagina": 2})

    assert len(primera.context["pagina"]) == 25 and len(segunda.context["pagina"]) == 2


# CP-44 en pantalla (RN-11, DEC-109)


def test_cp44_la_alerta_de_deuda_vencida_se_ve_en_el_estado(client, admin, cliente):
    client.force_login(admin)
    _cargar(client, cliente, monto="1200", dias_atras=31)

    html = client.get(_estado(cliente)).content.decode()

    assert "Tiene deuda vencida" in html and "$ 1.200,00" in html and "más de 30 días" in html


def test_cp44_sin_cargos_de_mas_de_30_dias_no_hay_alerta(client, admin, cliente):
    client.force_login(admin)
    _cargar(client, cliente, monto="1200", dias_atras=30)

    assert "Tiene deuda vencida" not in client.get(_estado(cliente)).content.decode()


# CP-122 y criterio 12 del spec: saldo inicial y su anulación (DEC-119, RI-18, DEC-114)


def test_criterio_12_saldo_inicial_por_la_pantalla(client, admin, cliente, efectivo):
    client.force_login(admin)

    assert _cargar(client, cliente).url == _estado(cliente)
    html = client.get(_estado(cliente)).content.decode()
    assert saldo(cliente) == Decimal("2000.00")
    assert "Tiene deuda vencida" in html and "Libreta del mostrador" in html

    repetido = _cargar(client, cliente, monto="100")
    assert repetido.status_code == 400
    assert "ya tiene un saldo inicial" in repetido.content.decode()

    cobro = registrar_cobro(admin, cliente, Decimal("500"), efectivo, entra_a_caja=False)
    rechazada = _anular_saldo(client, cliente)
    assert rechazada.status_code == 400
    assert "menor al monto del saldo inicial" in rechazada.content.decode()
    assert saldo(cliente) == Decimal("1500.00")

    anular_cobro(admin, cobro, "Error")
    assert _anular_saldo(client, cliente).url == _estado(cliente)
    assert saldo(cliente) == Decimal("0.00") and saldo_inicial_vigente(cliente) is None

    assert _cargar(client, cliente, monto="1800").url == _estado(cliente)
    assert saldo(cliente) == Decimal("1800.00")


def test_cp122_los_datos_invalidos_se_ven_junto_al_campo(client, admin, cliente):
    client.force_login(admin)

    sin_datos = client.post(reverse("clientes:saldo_inicial", args=[cliente.pk]), {})
    futura = _cargar(client, cliente, dias_atras=-1)

    assert set(sin_datos.context["form_saldo_inicial"].errors) == {
        "monto",
        "fecha_origen",
        "motivo",
    }
    assert "no puede ser posterior a hoy" in futura.content.decode()
    assert not MovimientoCuentaCorriente.objects.exists()


def test_cp122_sin_saldo_inicial_vigente_no_hay_nada_que_anular(client, admin, cliente):
    client.force_login(admin)

    assert _anular_saldo(client, cliente).status_code == 404


def test_cp122_la_anulacion_exige_motivo(client, admin, cliente):
    client.force_login(admin)
    _cargar(client, cliente)

    respuesta = _anular_saldo(client, cliente, motivo="")

    assert respuesta.status_code == 400
    assert saldo_inicial_vigente(cliente) is not None


def test_dec119_a_un_cliente_dado_de_baja_se_le_puede_cargar_el_saldo_inicial(
    client, admin, cliente
):
    cliente.activo = False
    cliente.save()
    client.force_login(admin)

    assert _cargar(client, cliente).url == _estado(cliente)
    assert saldo(cliente) == Decimal("2000.00")


# RF-41: límite y observaciones (DEC-108, DEC-112, DEC-115)


@pytest.mark.parametrize(
    ("limite", "esperado", "texto"),
    [
        ("", None, "Sin límite"),
        ("0", Decimal("0"), "Sin crédito habilitado"),
        ("1500", Decimal("1500"), "$ 1.500,00"),
    ],
)
def test_rf41_modifica_limite_y_observaciones(client, admin, cliente, limite, esperado, texto):
    client.force_login(admin)

    respuesta = client.post(
        reverse("clientes:condiciones", args=[cliente.pk]),
        {"limite_credito": limite, "observaciones": "  Paga los viernes "},
    )

    assert respuesta.url == _estado(cliente)
    cliente.refresh_from_db()
    assert cliente.limite_credito == esperado and cliente.observaciones == "Paga los viernes"
    assert texto in client.get(_estado(cliente)).content.decode()


def test_rf41_un_limite_negativo_se_rechaza_junto_al_campo(client, admin, cliente):
    client.force_login(admin)

    respuesta = client.post(
        reverse("clientes:condiciones", args=[cliente.pk]), {"limite_credito": "-1"}
    )

    assert respuesta.status_code == 400
    assert "limite_credito" in respuesta.context["form_condiciones"].errors
    cliente.refresh_from_db()
    assert cliente.limite_credito is None


def test_rf41_un_cliente_dado_de_baja_no_se_modifica(client, admin):
    baja = Cliente.objects.create(nombre="Dado de baja", activo=False)
    client.force_login(admin)

    html = client.get(_estado(baja)).content.decode()
    respuesta = client.post(
        reverse("clientes:condiciones", args=[baja.pk]), {"limite_credito": "0"}
    )

    assert "primero hay que reactivarlo" in html
    assert respuesta.status_code == 404
