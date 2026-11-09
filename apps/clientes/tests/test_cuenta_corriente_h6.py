"""Etapa 2 de H6: saldo acumulado (CP-146), comprobante del cobro (CP-147, CP-152) y corrección
de un cobro con la caja cerrada (CP-148)."""

import datetime
from decimal import Decimal
from unittest import mock

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import (
    Caja,
    CierreCajaDetalle,
    ConceptoMovimientoCaja,
    MovimientoCaja,
    TipoMovimientoCaja,
    Turno,
)
from apps.caja.services import abrir_caja, cerrar_caja
from apps.clientes import services as servicios
from apps.clientes.models import (
    EstadoPagoCliente,
    MovimientoCuentaCorriente,
    PagoCliente,
    TipoMovimientoCuentaCorriente,
)
from apps.clientes.services import (
    anular_cobro,
    comprobante_de_cobro,
    impedimento_para_anular_cobro,
    movimientos_de_cuenta,
    registrar_cobro,
    saldo,
)

pytestmark = pytest.mark.django_db

Tipo = TipoMovimientoCuentaCorriente


@pytest.fixture
def caja_hoy(cajera, efectivo):
    return abrir_caja(cajera, Turno.MANANA, Decimal("0.00"))


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


# CP-146: saldo acumulado por movimiento (L17, DEC-168, DEC-177)


def test_cp146_cada_movimiento_lleva_el_saldo_despues_de_el(admin, deudor, efectivo):
    _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    segundo = _cobrar(admin, deudor, "200", efectivo, entra_a_caja=False)
    anular_cobro(admin, segundo, "Error de carga")

    movimientos = list(movimientos_de_cuenta(admin, deudor))

    # Del más nuevo al más viejo: anulación, cobro de 200, cobro de 300, saldo inicial.
    assert [m.saldo_acumulado for m in movimientos] == [
        Decimal("700.00"),
        Decimal("500.00"),
        Decimal("700.00"),
        Decimal("1000.00"),
    ]
    assert movimientos[0].saldo_acumulado == saldo(deudor)


def test_cp146_con_la_misma_fecha_y_hora_desempata_el_orden_de_registro(admin, deudor, efectivo):
    _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    MovimientoCuentaCorriente.objects.update(fecha_hora=timezone.now())

    viejo_a_nuevo = list(movimientos_de_cuenta(admin, deudor))[::-1]

    assert [m.tipo for m in viejo_a_nuevo] == [Tipo.SALDO_INICIAL, Tipo.PAGO]
    assert [m.saldo_acumulado for m in viejo_a_nuevo] == [Decimal("1000.00"), Decimal("700.00")]


def test_cp146_el_saldo_acumulado_es_el_mismo_en_cualquier_pagina(client, admin, deudor, efectivo):
    for _ in range(27):
        _cobrar(admin, deudor, "10", efectivo, entra_a_caja=False)
    client.force_login(admin)
    url = reverse("clientes:estado", args=[deudor.pk])

    primera = client.get(url).context["pagina"].object_list
    segunda = client.get(url, {"pagina": 2}).context["pagina"].object_list

    assert primera[0].saldo_acumulado == saldo(deudor) == Decimal("730.00")
    assert segunda[-1].tipo == Tipo.SALDO_INICIAL
    assert segunda[-1].saldo_acumulado == Decimal("1000.00")
    # Página 2: los dos primeros cobros y el saldo inicial.
    assert [m.saldo_acumulado for m in segunda] == [
        Decimal("980.00"),
        Decimal("990.00"),
        Decimal("1000.00"),
    ]


def test_cp146_la_pantalla_muestra_la_columna_saldo(client, admin, deudor, efectivo):
    _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    client.force_login(admin)

    html = client.get(reverse("clientes:estado", args=[deudor.pk])).content.decode()

    assert ">Saldo</th>" in html
    assert "$ 700,00" in html and "$ 1.000,00" in html


# CP-147: comprobante del cobro (L16, DEC-167)


def test_cp147_saldo_anterior_y_posterior_de_cada_cobro(admin, deudor, efectivo):
    primero = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    segundo = _cobrar(admin, deudor, "200", efectivo, entra_a_caja=False)

    uno = comprobante_de_cobro(admin, primero.pk)
    dos = comprobante_de_cobro(admin, segundo.pk)

    # Lo que pasó después no cambia el comprobante de un cobro anterior.
    assert (uno.saldo_anterior, uno.saldo_posterior) == (Decimal("1000.00"), Decimal("700.00"))
    assert (dos.saldo_anterior, dos.saldo_posterior) == (Decimal("700.00"), Decimal("500.00"))


def test_cp147_el_comprobante_tiene_los_datos_acordados(client, admin, deudor, efectivo):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    client.force_login(admin)

    html = client.get(reverse("clientes:comprobante", args=[cobro.pk])).content.decode()

    for dato in [
        f"Comprobante de cobro N.º {cobro.pk}",
        timezone.localtime(cobro.fecha_hora).strftime("%d/%m/%Y %H:%M"),
        deudor.nombre,
        "Efectivo",
        "Saldo anterior",
        "$ 1.000,00",
        "$ 300,00",
        "Saldo posterior",
        "$ 700,00",
        f"Cobró: {admin.get_full_name()}",
        "No válido como factura",
    ]:
        assert dato in html, dato
    assert "Volver al cobro" in html


def test_cp147_un_cobro_anulado_se_marca(client, admin, deudor, efectivo):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    anular_cobro(admin, cobro, "Error")
    client.force_login(admin)

    html = client.get(reverse("clientes:comprobante", args=[cobro.pk])).content.decode()

    assert "ANULADO el" in html


def test_cp147_el_detalle_del_cobro_enlaza_al_comprobante(client, admin, deudor, efectivo):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    client.force_login(admin)

    html = client.get(reverse("clientes:cobro", args=[cobro.pk])).content.decode()

    assert reverse("clientes:comprobante", args=[cobro.pk]) in html


def test_cp147_un_cobro_inexistente_da_404(client, admin):
    client.force_login(admin)

    assert client.get(reverse("clientes:comprobante", args=[999999])).status_code == 404


# CP-152: quién abre el comprobante (DEC-185)


def test_cp152_la_cajera_recibe_el_comprobante_al_cobrar(
    client, cajera, caja_hoy, efectivo, deudor
):
    client.force_login(cajera)

    respuesta = client.post(
        reverse("clientes:cobrar"),
        {"cliente": deudor.pk, "monto": "300", "medio_pago": efectivo.pk},
        follow=True,
    )

    html = respuesta.content.decode()
    assert "Comprobante de cobro N.º" in html and "Nuevo cobro" in html
    assert "$ 700,00" in html


def test_cp152_la_cajera_reimprime_los_de_la_caja_abierta_de_hoy(
    client, cajera, caja_hoy, efectivo, deudor
):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    client.force_login(cajera)

    pantalla = client.get(reverse("clientes:cobrar")).content.decode()

    assert "Cobros de esta caja" in pantalla
    assert reverse("clientes:comprobante", args=[cobro.pk]) in pantalla
    assert client.get(reverse("clientes:comprobante", args=[cobro.pk])).status_code == 200


def test_cp152_la_cajera_no_ve_los_de_una_caja_cerrada(client, cajera, caja_hoy, efectivo, deudor):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    cerrar_caja(cajera, {efectivo.pk: Decimal("300")})
    client.force_login(cajera)

    assert client.get(reverse("clientes:comprobante", args=[cobro.pk])).status_code == 403
    with pytest.raises(PermissionDenied):
        comprobante_de_cobro(cajera, cobro.pk)


def test_cp152_la_cajera_no_ve_los_de_una_caja_de_otro_dia(
    client, cajera, caja_hoy, efectivo, deudor
):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    Caja.objects.filter(pk=caja_hoy.pk).update(
        fecha=timezone.localdate() - datetime.timedelta(days=1)
    )
    client.force_login(cajera)

    assert client.get(reverse("clientes:comprobante", args=[cobro.pk])).status_code == 403
    assert "Cobros de esta caja" not in client.get(reverse("clientes:cobrar")).content.decode()


def test_cp152_la_cajera_no_ve_un_cobro_sin_caja(client, admin, cajera, caja_hoy, efectivo, deudor):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    client.force_login(cajera)

    assert client.get(reverse("clientes:comprobante", args=[cobro.pk])).status_code == 403


def test_cp152_la_cajera_sigue_sin_ver_el_detalle_ni_el_estado(
    client, cajera, caja_hoy, efectivo, deudor
):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    client.force_login(cajera)

    assert client.get(reverse("clientes:cobro", args=[cobro.pk])).status_code == 403
    assert client.get(reverse("clientes:estado", args=[deudor.pk])).status_code == 403


def test_cp152_los_duenios_no_abren_el_comprobante(client, duenio, admin, deudor, efectivo):
    cobro = _cobrar(admin, deudor, "300", efectivo, entra_a_caja=False)
    client.force_login(duenio)

    assert client.get(reverse("clientes:comprobante", args=[cobro.pk])).status_code == 403


# CP-148: corrección de un cobro con la caja cerrada (L15, DEC-166, DEC-178, DEC-179)


@pytest.fixture
def cobro_en_caja_cerrada(cajera, caja_hoy, efectivo, deudor):
    cobro = _cobrar(cajera, deudor, "300", efectivo)
    cerrar_caja(cajera, {efectivo.pk: Decimal("300")})
    return cobro


def _de_la_caja(caja):
    return list(MovimientoCaja.objects.filter(caja=caja).values_list("pk", flat=True))


def test_cp148_la_reversa_va_en_la_caja_abierta_y_la_cerrada_no_cambia(
    admin, cajera, caja_hoy, efectivo, deudor, cobro_en_caja_cerrada
):
    antes = _de_la_caja(caja_hoy)
    cierre_antes = list(CierreCajaDetalle.objects.filter(caja=caja_hoy).values())
    tarde = abrir_caja(cajera, Turno.TARDE, Decimal("500.00"))

    assert impedimento_para_anular_cobro(cobro_en_caja_cerrada) is None
    anular_cobro(admin, cobro_en_caja_cerrada, "Se cobró dos veces")

    reversa = MovimientoCaja.objects.get(concepto=ConceptoMovimientoCaja.ANULACION_COBRO)
    assert reversa.caja == tarde and reversa.tipo == TipoMovimientoCaja.EGRESO
    assert reversa.pago_cliente == cobro_en_caja_cerrada and reversa.monto == Decimal("300.00")
    assert reversa.usuario == admin and reversa.descripcion == "Se cobró dos veces"
    assert _de_la_caja(caja_hoy) == antes
    assert list(CierreCajaDetalle.objects.filter(caja=caja_hoy).values()) == cierre_antes
    cobro_en_caja_cerrada.refresh_from_db()
    assert cobro_en_caja_cerrada.estado == EstadoPagoCliente.ANULADO
    assert saldo(deudor) == Decimal("1000.00")


def test_cp148_la_caja_abierta_puede_ser_de_otro_dia(
    admin, cajera, efectivo, deudor, cobro_en_caja_cerrada
):
    tarde = abrir_caja(cajera, Turno.TARDE, Decimal("500.00"))
    Caja.objects.filter(pk=tarde.pk).update(fecha=timezone.localdate() - datetime.timedelta(days=1))

    anular_cobro(admin, cobro_en_caja_cerrada, "Error")

    assert MovimientoCaja.objects.get(concepto=ConceptoMovimientoCaja.ANULACION_COBRO).caja_id == (
        tarde.pk
    )


def test_cp148_sin_efectivo_en_la_caja_abierta_se_rechaza_sin_registrar_nada(
    admin, cajera, efectivo, deudor, cobro_en_caja_cerrada
):
    abrir_caja(cajera, Turno.TARDE, Decimal("100.00"))

    with pytest.raises(ValidationError) as error:
        anular_cobro(admin, cobro_en_caja_cerrada, "Error")

    assert error.value.code == "sin_efectivo_suficiente"
    cobro_en_caja_cerrada.refresh_from_db()
    assert cobro_en_caja_cerrada.estado == EstadoPagoCliente.VIGENTE
    assert not MovimientoCaja.objects.filter(
        concepto=ConceptoMovimientoCaja.ANULACION_COBRO
    ).exists()
    assert saldo(deudor) == Decimal("700.00")


def test_cp148_solo_el_administrador_corrige(cajera, efectivo, cobro_en_caja_cerrada):
    abrir_caja(cajera, Turno.TARDE, Decimal("500.00"))

    with pytest.raises(PermissionDenied):
        anular_cobro(cajera, cobro_en_caja_cerrada, "Error")


def test_cp148_el_motivo_es_obligatorio(admin, cajera, efectivo, cobro_en_caja_cerrada):
    abrir_caja(cajera, Turno.TARDE, Decimal("500.00"))

    with pytest.raises(ValidationError):
        anular_cobro(admin, cobro_en_caja_cerrada, "   ")


def test_cp148_el_detalle_avisa_donde_va_la_reversa(
    client, admin, cajera, efectivo, cobro_en_caja_cerrada
):
    tarde = abrir_caja(cajera, Turno.TARDE, Decimal("500.00"))
    client.force_login(admin)

    html = client.get(reverse("clientes:cobro", args=[cobro_en_caja_cerrada.pk])).content.decode()

    assert "ya se cerró y no cambia: la reversa va en la caja abierta del" in html
    assert tarde.fecha.strftime("%d/%m/%Y") in html and "turno tarde" in html


def test_cp148_el_cierre_de_la_caja_abierta_lista_la_reversa_con_la_fecha_del_cobro(
    client, admin, cajera, efectivo, cobro_en_caja_cerrada
):
    abrir_caja(cajera, Turno.TARDE, Decimal("500.00"))
    anular_cobro(admin, cobro_en_caja_cerrada, "Error")
    client.force_login(cajera)

    html = client.get(reverse("caja:cerrar")).content.decode()

    fecha = timezone.localtime(cobro_en_caja_cerrada.fecha_hora).strftime("%d/%m/%Y")
    assert f"cobro del {fecha}" in html
    assert PagoCliente.objects.count() == 1


def test_cp148_el_detalle_calcula_una_sola_vez_la_caja_de_la_reversa(
    client, admin, cajera, efectivo, cobro_en_caja_cerrada
):
    abrir_caja(cajera, Turno.TARDE, Decimal("500.00"))
    client.force_login(admin)

    with mock.patch(
        "apps.clientes.services.caja_que_recibe_la_reversa",
        wraps=servicios.caja_que_recibe_la_reversa,
    ) as calculo:
        client.get(reverse("clientes:cobro", args=[cobro_en_caja_cerrada.pk]))

    assert calculo.call_count == 1
