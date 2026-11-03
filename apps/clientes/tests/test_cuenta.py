"""Servicio de cuenta corriente (H4, etapa 1): saldo, disponible, límite, deuda vencida y saldo
inicial. CP-42, CP-44 y CP-119 (en el servicio) y CP-122; DEC-108, DEC-109, DEC-111, DEC-114,
DEC-115 y DEC-119.
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.clientes import services as cuenta
from apps.clientes.models import (
    Cliente,
    MovimientoCuentaCorriente,
    PagoCliente,
    TipoMovimientoCuentaCorriente,
)
from apps.ventas.models import Venta

pytestmark = pytest.mark.django_db

Tipo = TipoMovimientoCuentaCorriente
HOY = datetime.date(2026, 3, 1)


def _momento(dias_atras):
    """Mediodía de hace `dias_atras` días respecto de HOY, en la hora local."""
    fecha = HOY - datetime.timedelta(days=dias_atras)
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(12)))


@pytest.fixture
def libro(cliente, caja, usuario, efectivo):
    """Arma movimientos como los dejarán la venta (etapa 3) y el cobro (etapa 4)."""

    class Libro:
        def venta(self, monto, dias_atras=0, para=None):
            para = para or cliente
            venta = Venta.objects.create(
                caja=caja, usuario=usuario, medio_pago=efectivo, monto_total=Decimal(monto)
            )
            MovimientoCuentaCorriente.objects.create(
                cliente=para,
                tipo=Tipo.VENTA_FIADA,
                monto=Decimal(monto),
                venta=venta,
                fecha_hora=_momento(dias_atras),
            )
            return venta

        def anular_venta(self, venta, para=None):
            MovimientoCuentaCorriente.objects.create(
                cliente=para or cliente,
                tipo=Tipo.ANULACION_VENTA,
                monto=venta.monto_total,
                venta=venta,
            )

        def cobro(self, monto, dias_atras=0, para=None):
            para = para or cliente
            pago = PagoCliente.objects.create(
                cliente=para, monto=Decimal(monto), medio_pago=efectivo, usuario=usuario
            )
            MovimientoCuentaCorriente.objects.create(
                cliente=para,
                tipo=Tipo.PAGO,
                monto=Decimal(monto),
                pago_cliente=pago,
                fecha_hora=_momento(dias_atras),
            )
            return pago

        def anular_cobro(self, pago):
            MovimientoCuentaCorriente.objects.create(
                cliente=pago.cliente, tipo=Tipo.ANULACION_PAGO, monto=pago.monto, pago_cliente=pago
            )

        def saldo_inicial(self, monto, dias_atras, para=None):
            return MovimientoCuentaCorriente.objects.create(
                cliente=para or cliente,
                tipo=Tipo.SALDO_INICIAL,
                monto=Decimal(monto),
                fecha_origen=HOY - datetime.timedelta(days=dias_atras),
                motivo="Deuda anterior",
            )

    return Libro()


# CP-42: el saldo sale de los movimientos (DEC-21, DEC-113, DEC-119)


def test_cp42_cliente_sin_movimientos_tiene_saldo_cero(cliente):
    assert cuenta.saldo(cliente) == Decimal("0.00")


def test_cp42_saldo_suma_cargos_y_resta_cobros_con_sus_anulaciones(cliente, libro):
    libro.saldo_inicial("2000", dias_atras=60)
    libro.venta("1000")
    anulada = libro.venta("700")
    libro.anular_venta(anulada)
    libro.cobro("600")
    cobro_anulado = libro.cobro("300")
    libro.anular_cobro(cobro_anulado)

    # 2000 + 1000 + 700 - 700 - 600 - 300 + 300
    assert cuenta.saldo(cliente) == Decimal("2400.00")


def test_r7_saldos_del_listado_en_una_sola_consulta(cliente, libro, django_assert_num_queries):
    otro = Cliente.objects.create(nombre="Otro")
    sin_movimientos = Cliente.objects.create(nombre="Sin movimientos")
    libro.venta("1000")
    libro.venta("250", para=otro)
    libro.cobro("100", para=otro)

    with django_assert_num_queries(1):
        saldos = cuenta.saldos_de_clientes([cliente, otro, sin_movimientos])

    assert saldos == {
        cliente.pk: Decimal("1000.00"),
        otro.pk: Decimal("150.00"),
        sin_movimientos.pk: Decimal("0.00"),
    }


# DEC-108 y DEC-115: límite, disponible y cómo se muestra


@pytest.mark.parametrize(
    ("limite", "texto"),
    [
        (None, "Sin límite"),
        (Decimal("0"), "Sin crédito habilitado"),
        (Decimal("1000"), "$ 1.000,00"),
    ],
)
def test_dec115_texto_del_limite(cliente, limite, texto):
    cliente.limite_credito = limite

    assert cuenta.texto_limite(cliente) == texto


def test_dec108_disponible_es_el_limite_menos_el_saldo(cliente, libro):
    libro.venta("800")
    cliente.limite_credito = Decimal("1000")

    assert cuenta.disponible(cliente) == Decimal("200.00")


def test_dec108_sin_limite_no_hay_disponible(cliente, libro):
    libro.venta("800")

    assert cuenta.disponible(cliente) is None


def test_cp115_llegar_justo_al_limite_se_permite_y_pasarlo_no(cliente, libro):
    libro.venta("800")
    cliente.limite_credito = Decimal("1000")

    cuenta.validar_limite(cliente, Decimal("200"))
    with pytest.raises(ValidationError) as error:
        cuenta.validar_limite(cliente, Decimal("201"))

    assert error.value.code == "limite_superado"
    assert "disponible $ 200,00" in error.value.messages[0]


def test_cp115_sin_limite_se_acepta_cualquier_monto(cliente, libro):
    libro.venta("800")

    cuenta.validar_limite(cliente, Decimal("999999"))


def test_cp115_con_limite_cero_no_hay_credito(cliente):
    cliente.limite_credito = Decimal("0")

    with pytest.raises(ValidationError) as error:
        cuenta.validar_limite(cliente, Decimal("1"))

    assert error.value.code == "sin_credito"


# DEC-111 y DEC-114: el saldo nunca queda por debajo de 0


def test_dec111_un_abono_mayor_al_saldo_se_rechaza(cliente, libro):
    libro.venta("500")

    cuenta.validar_saldo_suficiente(cliente, Decimal("500"), "el cobro")
    with pytest.raises(ValidationError) as error:
        cuenta.validar_saldo_suficiente(cliente, Decimal("500.01"), "el cobro")

    assert error.value.code == "saldo_insuficiente"


# CP-44 y CP-119: deuda vencida con los cobros imputados a lo más antiguo (DEC-109)


def test_cp119_cobro_cubre_primero_el_cargo_mas_antiguo(cliente, libro):
    libro.venta("1000", dias_atras=40)
    libro.venta("500", dias_atras=5)
    libro.cobro("600", dias_atras=2)

    assert cuenta.saldo(cliente) == Decimal("900.00")
    assert cuenta.deuda_vencida(cliente, hoy=HOY) == Decimal("400.00")


def test_cp44_sin_cargos_de_mas_de_30_dias_no_hay_deuda_vencida(cliente, libro):
    libro.venta("1000", dias_atras=30)

    assert cuenta.deuda_vencida(cliente, hoy=HOY) == Decimal("0.00")


def test_cp44_un_cargo_de_31_dias_ya_esta_vencido(cliente, libro):
    libro.venta("1000", dias_atras=31)

    assert cuenta.deuda_vencida(cliente, hoy=HOY) == Decimal("1000.00")


def test_cp119_cobros_que_cubren_lo_viejo_no_dejan_deuda_vencida(cliente, libro):
    libro.venta("1000", dias_atras=40)
    libro.venta("500", dias_atras=5)
    libro.cobro("1000")

    assert cuenta.deuda_vencida(cliente, hoy=HOY) == Decimal("0.00")


def test_cp119_ventas_y_cobros_anulados_no_cuentan(cliente, libro):
    anulada = libro.venta("1000", dias_atras=50)
    libro.anular_venta(anulada)
    libro.venta("300", dias_atras=40)
    cobro = libro.cobro("300")
    libro.anular_cobro(cobro)

    assert cuenta.deuda_vencida(cliente, hoy=HOY) == Decimal("300.00")


def test_cp119_el_saldo_inicial_vence_por_su_fecha_de_origen(cliente, libro):
    libro.saldo_inicial("2000", dias_atras=45)
    libro.venta("500", dias_atras=50)
    libro.cobro("700")

    # El cobro cubre primero la venta (50 días) y después 200 del saldo inicial (45 días).
    assert cuenta.deuda_vencida(cliente, hoy=HOY) == Decimal("1800.00")


def test_r7_deudas_vencidas_del_listado_en_una_sola_consulta(
    cliente, libro, django_assert_num_queries
):
    otro = Cliente.objects.create(nombre="Otro")
    libro.venta("1000", dias_atras=40)
    libro.venta("200", dias_atras=10, para=otro)

    with django_assert_num_queries(1):
        vencidas = cuenta.deudas_vencidas_de_clientes([cliente, otro], hoy=HOY)

    assert vencidas == {cliente.pk: Decimal("1000.00"), otro.pk: Decimal("0.00")}


# CP-122: saldo inicial y su anulación (DEC-119, RI-18)


def _cargar(usuario, cliente, monto="2000", dias_atras=45, motivo="Deuda de la libreta"):
    return cuenta.cargar_saldo_inicial(
        usuario,
        cliente,
        Decimal(monto),
        timezone.localdate() - datetime.timedelta(days=dias_atras),
        motivo,
    )


def test_cp122_el_administrador_carga_el_saldo_inicial(admin, cliente):
    saldo_inicial = _cargar(admin, cliente)

    assert saldo_inicial.tipo == Tipo.SALDO_INICIAL
    assert cuenta.saldo(cliente) == Decimal("2000.00")
    assert cuenta.deuda_vencida(cliente) == Decimal("2000.00")


def test_cp122_el_saldo_inicial_no_se_valida_contra_el_limite(admin, cliente):
    cliente.limite_credito = Decimal("500")
    cliente.save()

    _cargar(admin, cliente, monto="2000")

    assert cuenta.saldo(cliente) == Decimal("2000.00")


@pytest.mark.parametrize("rol", ["cajera", "duenio"])
def test_cp122_solo_el_administrador_carga_y_anula(request, admin, cliente, rol):
    otro = request.getfixturevalue(rol)
    saldo_inicial = _cargar(admin, cliente)

    with pytest.raises(PermissionDenied):
        _cargar(otro, cliente)
    with pytest.raises(PermissionDenied):
        cuenta.anular_saldo_inicial(otro, saldo_inicial, "Error")


def test_cp122_ri18_un_solo_saldo_inicial_vigente(admin, cliente):
    _cargar(admin, cliente)

    with pytest.raises(ValidationError) as error:
        _cargar(admin, cliente, monto="100")

    assert error.value.code == "saldo_inicial_repetido"


def test_cp122_anularlo_lo_deja_en_cero_y_permite_cargar_otro(admin, cliente):
    saldo_inicial = _cargar(admin, cliente)

    anulacion = cuenta.anular_saldo_inicial(admin, saldo_inicial, "Monto mal cargado")

    assert anulacion.tipo == Tipo.ANULACION_SALDO_INICIAL
    assert anulacion.saldo_inicial == saldo_inicial
    assert anulacion.cliente == cliente
    assert cuenta.saldo(cliente) == Decimal("0.00")
    assert cuenta.saldo_inicial_vigente(cliente) is None
    _cargar(admin, cliente, monto="1800")
    assert cuenta.saldo(cliente) == Decimal("1800.00")


def test_cp122_dec114_con_saldo_menor_al_monto_la_anulacion_se_rechaza(admin, cliente, libro):
    saldo_inicial = _cargar(admin, cliente)
    libro.cobro("500")

    with pytest.raises(ValidationError) as error:
        cuenta.anular_saldo_inicial(admin, saldo_inicial, "Error")

    assert error.value.code == "saldo_insuficiente"
    assert cuenta.saldo(cliente) == Decimal("1500.00")


def test_cp122_no_se_anula_dos_veces(admin, cliente):
    saldo_inicial = _cargar(admin, cliente)
    cuenta.anular_saldo_inicial(admin, saldo_inicial, "Error")

    with pytest.raises(ValidationError):
        cuenta.anular_saldo_inicial(admin, saldo_inicial, "Otra vez")


def test_cp122_solo_se_anula_un_saldo_inicial(admin, cliente, libro):
    libro.venta("500")
    cargo = MovimientoCuentaCorriente.objects.get(tipo=Tipo.VENTA_FIADA)

    with pytest.raises(ValidationError):
        cuenta.anular_saldo_inicial(admin, cargo, "Error")


@pytest.mark.parametrize(
    ("campos", "campo_con_error"),
    [
        ({"monto": "0"}, "monto"),
        ({"monto": "10.005"}, "monto"),
        ({"monto": "10000000000"}, "monto"),
        ({"dias_atras": -1}, "fecha_origen"),
        ({"motivo": "  "}, "motivo"),
        ({"motivo": "x" * 256}, "motivo"),
    ],
)
def test_cp122_datos_invalidos_se_rechazan(admin, cliente, campos, campo_con_error):
    with pytest.raises(ValidationError) as error:
        _cargar(admin, cliente, **campos)

    assert campo_con_error in error.value.message_dict
    assert cuenta.saldo(cliente) == Decimal("0.00")


def test_cp122_sin_fecha_de_origen_se_rechaza(admin, cliente):
    with pytest.raises(ValidationError) as error:
        cuenta.cargar_saldo_inicial(admin, cliente, Decimal("100"), None, "Deuda")

    assert "fecha_origen" in error.value.message_dict


def test_cp122_la_anulacion_exige_motivo(admin, cliente):
    saldo_inicial = _cargar(admin, cliente)

    with pytest.raises(ValidationError) as error:
        cuenta.anular_saldo_inicial(admin, saldo_inicial, "")

    assert "motivo" in error.value.message_dict
