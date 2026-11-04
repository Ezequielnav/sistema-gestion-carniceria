"""CU-04 Registrar pago de cliente: cobro y anulación (H4, etapa 4).

CP-40, CP-41, CP-117 y CP-118; DEC-110, DEC-111, DEC-113, DEC-116; S-2, S-6, S-8 y S-11
(DEC-121, DEC-125, DEC-127, DEC-130); R-1.
"""

import datetime
import json
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import (
    Caja,
    ConceptoMovimientoCaja,
    MedioPago,
    MovimientoCaja,
    TipoMovimientoCaja,
    Turno,
)
from apps.caja.services import (
    abrir_caja,
    cerrar_caja,
    movimientos_de_cobros,
    registrar_egreso_otro,
    resumen_de_cierre,
)
from apps.clientes.models import (
    Cliente,
    EstadoPagoCliente,
    MovimientoCuentaCorriente,
    PagoCliente,
    TipoMovimientoCuentaCorriente,
)
from apps.clientes.services import (
    anular_cobro,
    impedimento_para_anular_cobro,
    registrar_cobro,
    saldo,
)

pytestmark = pytest.mark.django_db

Tipo = TipoMovimientoCuentaCorriente
COBRAR = reverse("clientes:cobrar")


@pytest.fixture
def caja_hoy(cajera, efectivo):
    return abrir_caja(cajera, Turno.MANANA, Decimal("0.00"))


@pytest.fixture
def tarjeta(db):
    return MedioPago.objects.create(nombre="Tarjeta")


@pytest.fixture
def cuenta_corriente(db):
    return MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)


@pytest.fixture
def deudor(cliente):
    """Un cliente que debe $ 1.000 (saldo inicial, DEC-119)."""
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        tipo=Tipo.SALDO_INICIAL,
        monto=Decimal("1000.00"),
        fecha_origen=timezone.localdate(),
        motivo="Deuda anterior",
    )
    return cliente


def _cobrar(usuario, cliente, monto, medio, **opciones):
    return registrar_cobro(usuario, cliente, Decimal(monto), medio, **opciones)


def _nada_cobrado():
    return not (
        PagoCliente.objects.exists()
        or MovimientoCuentaCorriente.objects.filter(tipo=Tipo.PAGO).exists()
        or MovimientoCaja.objects.exists()
    )


# CP-40 y CP-117: el cobro baja el saldo y entra a la caja de hoy con su medio


def test_cp40_la_cajera_cobra_en_efectivo_en_la_caja_abierta(cajera, caja_hoy, efectivo, deudor):
    cobro = _cobrar(cajera, deudor, "300", efectivo)

    assert cobro.entra_a_caja and cobro.estado == EstadoPagoCliente.VIGENTE
    assert saldo(deudor) == Decimal("700.00")
    abono = MovimientoCuentaCorriente.objects.get(tipo=Tipo.PAGO)
    assert (abono.pago_cliente, abono.monto, abono.cliente) == (cobro, Decimal("300"), deudor)
    ingreso = MovimientoCaja.objects.get()
    assert (ingreso.caja, ingreso.tipo, ingreso.concepto) == (
        caja_hoy,
        TipoMovimientoCaja.INGRESO,
        ConceptoMovimientoCaja.PAGO_CLIENTE,
    )
    assert (ingreso.monto, ingreso.medio_pago, ingreso.usuario) == (
        Decimal("300"),
        efectivo,
        cajera,
    )


def test_cp117_el_cobro_entra_a_caja_con_su_medio(cajera, caja_hoy, efectivo, tarjeta, deudor):
    _cobrar(cajera, deudor, "1000", tarjeta)

    assert MovimientoCaja.objects.get().medio_pago == tarjeta
    assert saldo(deudor) == Decimal("0.00")
    assert dict(resumen_de_cierre(caja_hoy)) == {
        efectivo: Decimal("0.00"),
        tarjeta: Decimal("1000"),
    }


def test_dec116_se_cobra_a_un_cliente_dado_de_baja_que_debe(cajera, caja_hoy, efectivo, deudor):
    deudor.activo = False
    deudor.save()

    _cobrar(cajera, deudor, "1000", efectivo)

    assert saldo(deudor) == Decimal("0.00")


# CP-41 y DEC-111: nunca más que el saldo


def test_cp41_un_cobro_mayor_al_saldo_se_rechaza_con_el_maximo(cajera, caja_hoy, efectivo, deudor):
    with pytest.raises(ValidationError) as error:
        _cobrar(cajera, deudor, "1000.01", efectivo)

    assert error.value.message_dict == {
        "monto": ["El saldo de Cliente de prueba es $ 1.000,00: es el máximo a cobrar."]
    }
    assert _nada_cobrado()


def test_dec111_sin_saldo_no_hay_nada_que_cobrar(cajera, caja_hoy, efectivo, cliente):
    with pytest.raises(ValidationError) as error:
        _cobrar(cajera, cliente, "1", efectivo)

    assert error.value.code == "sin_saldo"
    assert _nada_cobrado()


@pytest.mark.parametrize("monto", ["0", "-5", "10.005", "10000000000"])
def test_montos_invalidos_se_rechazan(cajera, caja_hoy, efectivo, deudor, monto):
    with pytest.raises(ValidationError) as error:
        _cobrar(cajera, deudor, monto, efectivo)

    assert "monto" in error.value.message_dict
    assert _nada_cobrado()


def test_dec110_no_se_cobra_con_cuenta_corriente_ni_con_un_medio_inactivo(
    cajera, caja_hoy, cuenta_corriente, deudor
):
    inactivo = MedioPago.objects.create(nombre="Cheque", activo=False)

    for medio in (cuenta_corriente, inactivo):
        with pytest.raises(ValidationError) as error:
            _cobrar(cajera, deudor, "100", medio)
        assert "medio_pago" in error.value.message_dict
    assert _nada_cobrado()


# DEC-110 y S-6: la cajera necesita la caja abierta de hoy; el Administrador elige


def test_dec110_la_cajera_sin_caja_abierta_no_cobra(cajera, efectivo, deudor):
    with pytest.raises(ValidationError) as error:
        _cobrar(cajera, deudor, "100", efectivo)

    assert error.value.code == "sin_caja"
    assert _nada_cobrado()


def test_dec110_con_la_caja_de_otro_dia_no_se_cobra_en_caja(cajera, efectivo, deudor):
    Caja.objects.create(
        fecha=timezone.localdate() - datetime.timedelta(days=1), turno=Turno.TARDE, usuario=cajera
    )

    with pytest.raises(ValidationError) as error:
        _cobrar(cajera, deudor, "100", efectivo)

    assert error.value.code == "caja_de_otro_dia"


def test_s6_la_cajera_siempre_cobra_en_caja(cajera, caja_hoy, efectivo, deudor):
    cobro = _cobrar(cajera, deudor, "100", efectivo, entra_a_caja=False)

    assert cobro.entra_a_caja and MovimientoCaja.objects.count() == 1


def test_s6_el_administrador_cobra_sin_caja(admin, efectivo, deudor):
    cobro = _cobrar(admin, deudor, "400", efectivo, entra_a_caja=False)

    assert not cobro.entra_a_caja
    assert not MovimientoCaja.objects.exists()
    assert saldo(deudor) == Decimal("600.00")


def test_s6_el_administrador_cobra_en_la_caja_que_abrio_la_cajera(
    admin, caja_hoy, efectivo, deudor
):
    _cobrar(admin, deudor, "400", efectivo)

    ingreso = MovimientoCaja.objects.get()
    assert ingreso.caja == caja_hoy and ingreso.usuario == admin


def test_s6_el_administrador_que_pide_caja_sin_caja_abierta_se_rechaza(admin, efectivo, deudor):
    with pytest.raises(ValidationError) as error:
        _cobrar(admin, deudor, "400", efectivo, entra_a_caja=True)

    assert error.value.code == "sin_caja"


def test_los_duenios_no_cobran(duenio, efectivo, deudor):
    with pytest.raises(PermissionDenied):
        _cobrar(duenio, deudor, "100", efectivo, entra_a_caja=False)


# CP-118: anulación con sus dos reversas (DEC-113)


def test_cp118_anular_un_cobro_de_caja_deja_sus_dos_reversas(
    admin, cajera, caja_hoy, efectivo, deudor
):
    cobro = _cobrar(cajera, deudor, "300", efectivo)

    anular_cobro(admin, cobro, "Se cargó dos veces")

    cobro.refresh_from_db()
    assert cobro.estado == EstadoPagoCliente.ANULADO
    assert (cobro.anulado_por_usuario, cobro.motivo_anulacion) == (admin, "Se cargó dos veces")
    reversa = MovimientoCuentaCorriente.objects.get(tipo=Tipo.ANULACION_PAGO)
    assert (reversa.pago_cliente, reversa.monto) == (cobro, Decimal("300"))
    egreso = MovimientoCaja.objects.get(concepto=ConceptoMovimientoCaja.ANULACION_COBRO)
    assert (egreso.caja, egreso.tipo, egreso.monto, egreso.medio_pago, egreso.usuario) == (
        caja_hoy,
        TipoMovimientoCaja.EGRESO,
        Decimal("300"),
        efectivo,
        admin,
    )
    assert egreso.descripcion == "Se cargó dos veces"
    assert saldo(deudor) == Decimal("1000.00")
    assert dict(resumen_de_cierre(caja_hoy))[efectivo] == Decimal("0.00")


def test_cp118_un_cobro_sin_caja_se_anula_siempre_sin_reversa_de_caja(admin, efectivo, deudor):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)

    anular_cobro(admin, cobro, "Error")

    assert not MovimientoCaja.objects.exists()
    assert saldo(deudor) == Decimal("1000.00")


def test_cp118_dec113_con_la_caja_cerrada_no_se_anula(admin, cajera, caja_hoy, efectivo, deudor):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    cerrar_caja(cajera, {efectivo.pk: Decimal("300")})

    assert "ya se cerró" in impedimento_para_anular_cobro(cobro)
    with pytest.raises(ValidationError) as error:
        anular_cobro(admin, cobro, "Error")

    assert error.value.code == "caja_cerrada"
    cobro.refresh_from_db()
    assert cobro.estado == EstadoPagoCliente.VIGENTE
    assert saldo(deudor) == Decimal("700.00")


def test_cp118_dec69_sin_efectivo_para_devolver_no_se_anula(
    admin, cajera, caja_hoy, efectivo, deudor
):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    registrar_egreso_otro(cajera, Decimal("250"), "Retiro")

    with pytest.raises(ValidationError) as error:
        anular_cobro(admin, cobro, "Error")

    assert error.value.code == "sin_efectivo_suficiente"
    assert not MovimientoCaja.objects.filter(
        concepto=ConceptoMovimientoCaja.ANULACION_COBRO
    ).exists()


def test_cp118_no_se_anula_dos_veces(admin, efectivo, deudor):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    anular_cobro(admin, cobro, "Error")

    with pytest.raises(ValidationError):
        anular_cobro(admin, cobro, "Otra vez")
    assert impedimento_para_anular_cobro(PagoCliente.objects.get()) == "El cobro ya está anulado."


@pytest.mark.parametrize("quien", ["cajera", "duenio"])
def test_cp118_solo_el_administrador_anula(request, admin, efectivo, deudor, quien):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)

    with pytest.raises(PermissionDenied):
        anular_cobro(request.getfixturevalue(quien), cobro, "Error")


def test_cp118_la_anulacion_exige_motivo(admin, efectivo, deudor):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)

    with pytest.raises(ValidationError) as error:
        anular_cobro(admin, cobro, "  ")

    assert "motivo" in error.value.message_dict


# S-8: cobros y reversas en el cierre y su reporte


def test_s8_el_cierre_lista_los_cobros_y_sus_reversas(
    client, admin, cajera, caja_hoy, efectivo, deudor
):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    _cobrar(cajera, deudor, "200", efectivo)
    anular_cobro(admin, cobro, "Error")
    client.force_login(cajera)

    assert [m.concepto for m in movimientos_de_cobros(caja_hoy)] == [
        ConceptoMovimientoCaja.PAGO_CLIENTE,
        ConceptoMovimientoCaja.PAGO_CLIENTE,
        ConceptoMovimientoCaja.ANULACION_COBRO,
    ]
    cerrar = client.get(reverse("caja:cerrar")).content.decode()
    assert "Cobros de cuenta corriente" in cerrar and "Cliente de prueba" in cerrar
    cerrar_caja(cajera, {efectivo.pk: Decimal("200")})
    reporte = client.get(reverse("caja:cierre", args=[caja_hoy.pk])).content.decode()
    assert "Cobros de cuenta corriente" in reporte and "Anulación de cobro" in reporte
    # La etiqueta del concepto PAGO_CLIENTE (el valor guardado no cambia).
    assert f"Cobro de cuenta corriente N.º {cobro.pk}" in reporte


# Pantallas (S-2, S-6)


def test_s2_la_cajera_tiene_cobrar_cuenta_corriente_en_el_menu(client, cajera):
    client.force_login(cajera)

    assert f'href="{COBRAR}"' in client.get(reverse("inicio")).content.decode()


def test_la_cajera_sin_caja_de_hoy_ve_el_aviso(client, cajera):
    client.force_login(cajera)

    html = client.get(COBRAR).content.decode()

    assert "No hay una caja abierta de hoy" in html and 'id="cobro"' not in html


def test_s6_la_pantalla_de_la_cajera_no_tiene_entra_a_caja_y_ofrece_medios_sin_cuenta_corriente(
    client, cajera, caja_hoy, efectivo, cuenta_corriente
):
    client.force_login(cajera)

    respuesta = client.get(COBRAR)

    opciones = [str(e) for _, e in respuesta.context["form"].fields["medio_pago"].choices]
    assert opciones == ["Elegí un medio de pago", "Efectivo"]
    assert "Entra a la caja abierta" not in respuesta.content.decode()


def test_cp40_la_cajera_cobra_desde_la_pantalla(client, cajera, caja_hoy, efectivo, deudor):
    client.force_login(cajera)

    respuesta = client.post(
        COBRAR, {"cliente": deudor.pk, "monto": "300", "medio_pago": efectivo.pk}
    )

    assert respuesta.url == COBRAR
    assert saldo(deudor) == Decimal("700.00")
    mensaje = list(client.get(COBRAR).context["messages"])[0]
    assert "Se registró el cobro" in str(mensaje) and "$ 300,00" in str(mensaje)


def test_cp41_el_error_del_monto_se_ve_y_el_cliente_queda_elegido(
    client, cajera, caja_hoy, efectivo, deudor
):
    client.force_login(cajera)

    respuesta = client.post(
        COBRAR, {"cliente": deudor.pk, "monto": "5000", "medio_pago": efectivo.pk}
    )

    assert "es el máximo a cobrar" in respuesta.content.decode()
    assert respuesta.context["cliente_inicial"]["id"] == deudor.pk
    assert not PagoCliente.objects.exists()


def test_sin_cliente_elegido_se_pide_elegirlo(client, cajera, caja_hoy, efectivo):
    client.force_login(cajera)

    respuesta = client.post(COBRAR, {"monto": "300", "medio_pago": efectivo.pk})

    assert "Elegí el cliente al que le cobrás." in respuesta.content.decode()


def test_s6_el_administrador_con_caja_de_hoy_elige_si_entra(
    client, admin, caja_hoy, efectivo, deudor
):
    client.force_login(admin)

    assert "Entra a la caja abierta" in client.get(COBRAR).content.decode()
    respuesta = client.post(
        COBRAR, {"cliente": deudor.pk, "monto": "300", "medio_pago": efectivo.pk}
    )

    cobro = PagoCliente.objects.get()
    assert respuesta.url == reverse("clientes:cobro", args=[cobro.pk])
    assert not cobro.entra_a_caja and not MovimientoCaja.objects.exists()


def test_s6_el_administrador_sin_caja_cobra_sin_movimiento(client, admin, efectivo, deudor):
    client.force_login(admin)

    html = client.get(COBRAR).content.decode()
    client.post(
        COBRAR,
        {"cliente": deudor.pk, "monto": "300", "medio_pago": efectivo.pk, "entra_a_caja": "on"},
    )

    assert "se registra sin movimiento de caja" in html
    assert not PagoCliente.objects.get().entra_a_caja


def test_desde_el_listado_el_cliente_llega_elegido(client, admin, deudor):
    client.force_login(admin)

    respuesta = client.get(COBRAR, {"cliente": deudor.pk})

    inicial = respuesta.context["cliente_inicial"]
    assert (inicial["id"], inicial["saldo"]) == (deudor.pk, "1000.00")
    assert (
        f"{COBRAR}?cliente={deudor.pk}" in client.get(reverse("clientes:clientes")).content.decode()
    )
    datos = json.loads(
        respuesta.content.decode()
        .split('id="cliente-inicial" type="application/json">')[1]
        .split("</script>")[0]
    )
    assert datos["nombre"] == "Cliente de prueba"


def test_el_detalle_y_la_anulacion_por_la_pantalla(
    client, admin, cajera, caja_hoy, efectivo, deudor
):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    client.force_login(admin)
    detalle = reverse("clientes:cobro", args=[cobro.pk])

    assert "Anular cobro" in client.get(detalle).content.decode()
    sin_motivo = client.post(reverse("clientes:cobro_anular", args=[cobro.pk]), {"motivo": ""})
    respuesta = client.post(reverse("clientes:cobro_anular", args=[cobro.pk]), {"motivo": "Error"})

    assert sin_motivo.status_code == 400
    assert respuesta.url == detalle
    assert "Anulado" in client.get(detalle).content.decode()


def test_la_anulacion_con_la_caja_cerrada_muestra_el_motivo(
    client, admin, cajera, caja_hoy, efectivo, deudor
):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    cerrar_caja(cajera, {efectivo.pk: Decimal("300")})
    client.force_login(admin)

    html = client.get(reverse("clientes:cobro", args=[cobro.pk])).content.decode()

    assert "un cobro que entró a caja se anula solo con su caja abierta" in html
    assert 'action="' + reverse("clientes:cobro_anular", args=[cobro.pk]) not in html


@pytest.mark.parametrize("quien", ["cajera", "cajera_alta", "duenio"])
def test_detalle_y_anulacion_son_del_administrador(client, request, admin, efectivo, deudor, quien):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    client.force_login(request.getfixturevalue(quien))

    assert client.get(reverse("clientes:cobro", args=[cobro.pk])).status_code == 403
    assert (
        client.post(reverse("clientes:cobro_anular", args=[cobro.pk]), {"motivo": "X"}).status_code
        == 403
    )


def test_los_duenios_no_entran_al_cobro(client, duenio):
    client.force_login(duenio)

    assert client.get(COBRAR).status_code == 403


def test_sc01_en_el_cobro_la_cajera_ve_los_dados_de_baja_que_deben(client, cajera, deudor):
    deudor.activo = False
    deudor.save()
    Cliente.objects.create(nombre="Cliente sin deuda", activo=False)
    client.force_login(cajera)

    datos = client.get(reverse("clientes:buscar"), {"q": "cliente", "para": "cobro"}).json()

    assert [r["id"] for r in datos["resultados"]] == [deudor.pk]
