"""CU-07 pago a proveedor, ingreso al contado y anulación de pagos (H3, etapa 4).

CP-33 a CP-36, CP-90 a CP-92 y CP-102; DEC-80, DEC-81, DEC-92 y DEC-104.
"""

import datetime
import json
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
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
from apps.caja.services import abrir_caja, cerrar_caja
from apps.proveedores.models import (
    CondicionPago,
    EstadoIngreso,
    EstadoPago,
    IngresoMercaderia,
    PagoProveedor,
    ProductoProveedor,
)
from apps.proveedores.services import (
    anular_ingreso,
    anular_pago,
    ingresos_con_saldo,
    registrar_ingreso,
    registrar_pago,
    saldo_de_ingreso,
    saldo_de_proveedor,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def transferencia(db):
    return MedioPago.objects.create(nombre="Transferencia", es_transferencia=True)


@pytest.fixture
def tarjeta(db):
    return MedioPago.objects.create(nombre="Tarjeta")


@pytest.fixture
def caja_de_hoy(usuario, efectivo):
    # La abre la cajera, con $ 3.000 de fondo; el Administrador paga desde ella (DEC-80).
    return abrir_caja(usuario, Turno.MANANA, Decimal("3000.00"))


@pytest.fixture
def ingreso_2000(admin, proveedor, producto):
    return registrar_ingreso(admin, proveedor, [(producto.pk, Decimal("2"), Decimal("1000"))])


def _movimientos_de_pagos():
    return MovimientoCaja.objects.filter(
        concepto__in=[ConceptoMovimientoCaja.PAGO_PROVEEDOR, ConceptoMovimientoCaja.ANULACION_PAGO]
    )


# CP-33, CP-90: transferencia


def test_cp33_cp90_pago_por_transferencia_baja_el_saldo_sin_caja(
    admin, proveedor, ingreso_2000, transferencia
):
    pago = registrar_pago(admin, ingreso_2000, Decimal("500"), transferencia)

    assert (pago.proveedor, pago.usuario, pago.estado) == (proveedor, admin, EstadoPago.VIGENTE)
    assert saldo_de_ingreso(ingreso_2000) == Decimal("1500")
    assert saldo_de_proveedor(proveedor) == Decimal("1500.00")
    assert not MovimientoCaja.objects.exists()  # tampoco hizo falta caja abierta
    assert ingresos_con_saldo() == [ingreso_2000]


@pytest.mark.parametrize("medio", ["tarjeta", "cuenta_corriente"])
def test_cp90_otros_medios_se_rechazan(request, admin, ingreso_2000, transferencia, medio):
    if medio == "cuenta_corriente":
        otro = MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)
    else:
        otro = request.getfixturevalue(medio)

    with pytest.raises(ValidationError) as error:
        registrar_pago(admin, ingreso_2000, Decimal("100"), otro)

    assert "efectivo o por transferencia" in error.value.messages[0]
    assert not PagoProveedor.objects.exists()


# CP-34, CP-35 (RI-08, RI-14)


def test_cp34_los_pagos_no_superan_el_total(admin, ingreso_2000, transferencia):
    registrar_pago(admin, ingreso_2000, Decimal("1500"), transferencia)

    with pytest.raises(ValidationError) as error:
        registrar_pago(admin, ingreso_2000, Decimal("500.01"), transferencia)
    assert "$ 500,00" in error.value.message_dict["monto"][0]

    registrar_pago(admin, ingreso_2000, Decimal("500"), transferencia)
    assert saldo_de_ingreso(ingreso_2000) == 0
    assert ingresos_con_saldo() == []


@pytest.mark.parametrize("monto", ["0", "-1", "10.001"])
def test_el_monto_es_positivo_y_con_centavos(admin, ingreso_2000, transferencia, monto):
    with pytest.raises(ValidationError):
        registrar_pago(admin, ingreso_2000, Decimal(monto), transferencia)


def test_cp35_ingreso_de_otro_proveedor_se_rechaza(admin, ingreso_2000, transferencia):
    from apps.proveedores.models import Proveedor

    otro = Proveedor.objects.create(nombre="Otro proveedor")
    with pytest.raises(ValidationError) as error:
        registrar_pago(admin, ingreso_2000, Decimal("100"), transferencia, proveedor=otro)
    assert "otro proveedor" in error.value.messages[0]


def test_un_ingreso_anulado_o_de_un_proveedor_dado_de_baja_no_recibe_pagos(
    admin, proveedor, ingreso_2000, transferencia
):
    proveedor.activo = False
    proveedor.save()
    with pytest.raises(ValidationError):
        registrar_pago(admin, ingreso_2000, Decimal("100"), transferencia)

    proveedor.activo = True
    proveedor.save()
    anular_ingreso(admin, ingreso_2000, "Error")
    with pytest.raises(ValidationError):
        registrar_pago(admin, ingreso_2000, Decimal("100"), transferencia)


# CP-36, CP-91: efectivo


def test_cp36_supera_el_efectivo_disponible_y_muestra_el_maximo(
    admin, proveedor, producto, efectivo, usuario
):
    caja = abrir_caja(usuario, Turno.MANANA, Decimal("1200.00"))
    ingreso = registrar_ingreso(admin, proveedor, [(producto.pk, Decimal("2"), Decimal("1000"))])

    with pytest.raises(ValidationError) as error:
        registrar_pago(admin, ingreso, Decimal("1200.01"), efectivo)
    assert "$ 1.200,00" in error.value.message_dict["monto"][0]
    assert not PagoProveedor.objects.exists() and not MovimientoCaja.objects.exists()

    pago = registrar_pago(admin, ingreso, Decimal("1200.00"), efectivo)
    egreso = MovimientoCaja.objects.get()
    assert (egreso.caja, egreso.tipo, egreso.concepto) == (
        caja,
        TipoMovimientoCaja.EGRESO,
        ConceptoMovimientoCaja.PAGO_PROVEEDOR,
    )
    assert (egreso.monto, egreso.medio_pago, egreso.pago_proveedor) == (
        Decimal("1200.00"),
        efectivo,
        pago,
    )
    # La caja la abrió la cajera; el egreso queda a nombre del Administrador (DEC-80).
    assert caja.usuario == usuario and egreso.usuario == admin


def test_cp91_efectivo_sin_caja_abierta_o_con_la_de_otro_dia(
    admin, usuario, ingreso_2000, efectivo
):
    with pytest.raises(ValidationError) as error:
        registrar_pago(admin, ingreso_2000, Decimal("100"), efectivo)
    assert error.value.code == "sin_caja"

    Caja.objects.create(
        fecha=timezone.localdate() - datetime.timedelta(days=1),
        turno=Turno.TARDE,
        usuario=usuario,
        monto_inicial=Decimal("5000"),
    )
    with pytest.raises(ValidationError) as error:
        registrar_pago(admin, ingreso_2000, Decimal("100"), efectivo)
    assert error.value.code == "caja_de_otro_dia"
    assert not PagoProveedor.objects.exists()


# CP-92: contado


def test_cp92_contado_en_efectivo_guarda_todo_junto(
    admin, proveedor, producto, efectivo, caja_de_hoy
):
    ingreso = registrar_ingreso(
        admin,
        proveedor,
        [(producto.pk, Decimal("2"), Decimal("1000"))],
        condicion=CondicionPago.CONTADO,
        medio=efectivo,
    )

    assert ingreso.condicion_pago == CondicionPago.CONTADO
    pago = PagoProveedor.objects.get()
    assert (pago.ingreso, pago.monto) == (ingreso, Decimal("2000.00"))
    assert MovimientoCaja.objects.get().pago_proveedor == pago
    assert saldo_de_ingreso(ingreso) == 0 and saldo_de_proveedor(proveedor) == 0
    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("2")


def test_cp92_contado_por_transferencia_sin_caja(admin, proveedor, producto, transferencia):
    registrar_ingreso(
        admin,
        proveedor,
        [(producto.pk, Decimal("1"), Decimal("1000"))],
        condicion=CondicionPago.CONTADO,
        medio=transferencia,
    )

    assert PagoProveedor.objects.get().medio_pago == transferencia
    assert not MovimientoCaja.objects.exists()


def test_cp92_si_el_pago_se_rechaza_no_se_guarda_nada(
    admin, proveedor, producto, efectivo, usuario
):
    abrir_caja(usuario, Turno.MANANA, Decimal("500.00"))

    with pytest.raises(ValidationError) as error:
        registrar_ingreso(
            admin,
            proveedor,
            [(producto.pk, Decimal("2"), Decimal("1000"))],
            condicion=CondicionPago.CONTADO,
            medio=efectivo,
        )

    assert "$ 500,00" in error.value.messages[0]
    assert not IngresoMercaderia.objects.exists() and not PagoProveedor.objects.exists()
    assert not MovimientoCaja.objects.exists() and not ProductoProveedor.objects.exists()
    producto.refresh_from_db()
    assert producto.stock_actual == 0


def test_el_contado_pide_un_medio_valido(admin, proveedor, producto, tarjeta):
    for medio in (None, tarjeta):
        with pytest.raises(ValidationError):
            registrar_ingreso(
                admin,
                proveedor,
                [(producto.pk, Decimal("1"), Decimal("10"))],
                condicion=CondicionPago.CONTADO,
                medio=medio,
            )
    assert not IngresoMercaderia.objects.exists()


# CP-102: anulación del pago


def test_cp102_anular_transferencia_sube_el_saldo(admin, ingreso_2000, transferencia):
    pago = registrar_pago(admin, ingreso_2000, Decimal("500"), transferencia)

    anular_pago(admin, pago, "  Se cargó dos veces ")

    pago.refresh_from_db()
    assert pago.estado == EstadoPago.ANULADO
    assert (pago.anulado_por_usuario, pago.motivo_anulacion) == (admin, "Se cargó dos veces")
    assert saldo_de_ingreso(ingreso_2000) == Decimal("2000")
    assert not MovimientoCaja.objects.exists()
    with pytest.raises(ValidationError):
        anular_pago(admin, pago, "Otra vez")


def test_cp102_anular_efectivo_con_su_caja_abierta_deja_una_reversa(
    admin, ingreso_2000, efectivo, caja_de_hoy
):
    pago = registrar_pago(admin, ingreso_2000, Decimal("800"), efectivo)

    anular_pago(admin, pago, "Monto equivocado")

    egreso, reversa = _movimientos_de_pagos().order_by("pk")
    assert egreso.concepto == ConceptoMovimientoCaja.PAGO_PROVEEDOR and egreso.monto == 800
    assert (reversa.tipo, reversa.concepto, reversa.pago_proveedor) == (
        TipoMovimientoCaja.INGRESO,
        ConceptoMovimientoCaja.ANULACION_PAGO,
        pago,
    )
    assert (reversa.caja, reversa.monto, reversa.usuario) == (caja_de_hoy, Decimal("800"), admin)
    assert reversa.descripcion == "Monto equivocado"
    assert saldo_de_ingreso(ingreso_2000) == Decimal("2000")
    # La base no admite una segunda reversa del mismo pago.
    with pytest.raises(IntegrityError), transaction.atomic():
        MovimientoCaja.objects.create(
            caja=caja_de_hoy,
            tipo=TipoMovimientoCaja.INGRESO,
            monto=Decimal("800"),
            medio_pago=efectivo,
            concepto=ConceptoMovimientoCaja.ANULACION_PAGO,
            pago_proveedor=pago,
            usuario=admin,
        )


def test_cp102_con_la_caja_del_egreso_cerrada_se_rechaza(
    admin, usuario, ingreso_2000, efectivo, caja_de_hoy
):
    pago = registrar_pago(admin, ingreso_2000, Decimal("800"), efectivo)
    cerrar_caja(usuario, {efectivo.pk: Decimal("2200.00")})

    with pytest.raises(ValidationError) as error:
        anular_pago(admin, pago, "Tarde")

    assert error.value.code == "caja_cerrada"
    pago.refresh_from_db()
    assert pago.estado == EstadoPago.VIGENTE
    assert _movimientos_de_pagos().count() == 1


def test_cp101_el_ingreso_se_anula_cuando_sus_pagos_estan_anulados(
    admin, ingreso_2000, transferencia
):
    pago = registrar_pago(admin, ingreso_2000, Decimal("500"), transferencia)
    with pytest.raises(ValidationError):
        anular_ingreso(admin, ingreso_2000, "Error")

    anular_pago(admin, pago, "Error")
    anular_ingreso(admin, ingreso_2000, "Error")

    ingreso_2000.refresh_from_db()
    assert ingreso_2000.estado == EstadoIngreso.ANULADO


def test_el_motivo_de_la_anulacion_es_obligatorio(admin, ingreso_2000, transferencia):
    pago = registrar_pago(admin, ingreso_2000, Decimal("500"), transferencia)
    for motivo in ("  ", "x" * 256):
        with pytest.raises(ValidationError):
            anular_pago(admin, pago, motivo)


@pytest.mark.parametrize("quien", ["cajera_alta", "cajera", "duenio"])
def test_pagos_y_anulaciones_son_solo_del_administrador(
    request, admin, ingreso_2000, transferencia, quien
):
    usuario = request.getfixturevalue(quien)
    pago = registrar_pago(admin, ingreso_2000, Decimal("500"), transferencia)

    with pytest.raises(PermissionDenied):
        registrar_pago(usuario, ingreso_2000, Decimal("100"), transferencia)
    with pytest.raises(PermissionDenied):
        anular_pago(usuario, pago, "No")
    assert PagoProveedor.objects.count() == 1


# DEC-104: medio de transferencia


def test_dec104_un_solo_medio_de_transferencia_y_no_puede_ser_efectivo(transferencia):
    with pytest.raises(IntegrityError), transaction.atomic():
        MedioPago.objects.create(nombre="Otra transferencia", es_transferencia=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        MedioPago.objects.create(nombre="Mixto", es_efectivo=True, es_transferencia=True)


# Pantallas


def test_registrar_pago_desde_la_pantalla(client, admin, ingreso_2000, transferencia, efectivo):
    client.force_login(admin)
    url = reverse("proveedores:pago_nuevo")

    form = client.get(url, {"ingreso": ingreso_2000.pk}).context["form"]
    assert form.initial == {"ingreso": ingreso_2000.pk, "monto": Decimal("2000")}
    assert {m.nombre for m in form.fields["medio_pago"].queryset} == {"Efectivo", "Transferencia"}

    sin_caja = client.post(
        url, {"ingreso": ingreso_2000.pk, "monto": "500", "medio_pago": efectivo.pk}
    )
    assert "No hay una caja abierta." in sin_caja.content.decode()

    respuesta = client.post(
        url, {"ingreso": ingreso_2000.pk, "monto": "500", "medio_pago": transferencia.pk}
    )
    pago = PagoProveedor.objects.get()
    assert respuesta.url == reverse("proveedores:pago", args=[pago.pk])
    detalle = client.get(respuesta.url).content.decode()
    assert "$ 500,00" in detalle and "Anular pago" in detalle
    assert (
        f"Pago N.º {pago.pk}"
        in client.get(reverse("proveedores:ingreso", args=[ingreso_2000.pk])).content.decode()
    )
    assert "Transferencia" in client.get(reverse("proveedores:pagos")).content.decode()

    anulado = client.post(reverse("proveedores:pago_anular", args=[pago.pk]), {"motivo": "Error"})
    assert anulado.url == respuesta.url
    pago.refresh_from_db()
    assert pago.estado == EstadoPago.ANULADO


def test_ingreso_al_contado_desde_la_pantalla(client, admin, proveedor, producto, transferencia):
    client.force_login(admin)

    respuesta = client.post(
        reverse("proveedores:ingreso_confirmar"),
        {
            "proveedor": proveedor.pk,
            "condicion_pago": "CONTADO",
            "medio_pago": transferencia.pk,
            "lineas": json.dumps([{"producto": producto.pk, "cantidad": "1", "precio": "100"}]),
        },
    )

    assert "detalle" in respuesta.json()
    assert PagoProveedor.objects.get().monto == Decimal("100.00")


@pytest.mark.parametrize("quien", ["cajera_alta", "cajera", "duenio"])
def test_las_pantallas_de_pagos_dan_403(client, request, admin, ingreso_2000, transferencia, quien):
    pago = registrar_pago(admin, ingreso_2000, Decimal("500"), transferencia)
    client.force_login(request.getfixturevalue(quien))

    for url in (
        reverse("proveedores:pagos"),
        reverse("proveedores:pago_nuevo"),
        reverse("proveedores:pago", args=[pago.pk]),
    ):
        assert client.get(url).status_code == 403, url
    for url in (
        reverse("proveedores:pago_nuevo"),
        reverse("proveedores:pago_anular", args=[pago.pk]),
    ):
        assert client.post(url, {}).status_code == 403, url
