"""CU-01: reglas de apps/ventas/services.py (CP-10 a CP-17, CP-20, CP-21, CP-82, CP-83)."""

from decimal import Decimal
from unittest import mock

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.caja.models import (
    ConceptoMovimientoCaja,
    EstadoCaja,
    MedioPago,
    MovimientoCaja,
    TipoMovimientoCaja,
    Turno,
)
from apps.caja.services import abrir_caja
from apps.catalogo.models import Producto, UnidadMedida
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import DetalleVenta, Venta
from apps.ventas.services import (
    buscar_para_venta,
    medios_de_pago_para_venta,
    registrar_venta,
    subtotal,
)

pytestmark = pytest.mark.django_db


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


@pytest.fixture
def cuenta_corriente(db):
    return MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)


def _nada_guardado():
    return not (
        Venta.objects.exists() or DetalleVenta.objects.exists() or MovimientoCaja.objects.exists()
    )


# CP-10, CP-11, CP-12, CP-13 y CP-20


def test_cp10_cp11_venta_con_varios_productos(usuario, caja_hoy, efectivo, aceite, asado):
    venta, avisos = registrar_venta(
        usuario, [(aceite.pk, Decimal("2")), (asado.pk, Decimal("1.250"))], efectivo
    )

    detalles = {d.producto_id: d for d in venta.detalleventa_set.all()}
    assert detalles[aceite.pk].precio_unitario == Decimal("2500.00")
    assert detalles[aceite.pk].subtotal == Decimal("5000.00")
    assert detalles[asado.pk].subtotal == Decimal("12250.00")
    assert venta.monto_total == Decimal("17250.00")
    assert venta.caja == caja_hoy and venta.usuario == usuario and venta.medio_pago == efectivo
    movimiento = MovimientoCaja.objects.get()
    assert movimiento.tipo == TipoMovimientoCaja.INGRESO
    assert movimiento.concepto == ConceptoMovimientoCaja.VENTA
    assert movimiento.venta == venta and movimiento.caja == caja_hoy
    assert movimiento.monto == venta.monto_total and movimiento.medio_pago == efectivo
    assert avisos == []


def test_cp12_cp13_cp20_el_stock_baja_solo_si_se_controla(
    usuario, caja_hoy, efectivo, aceite, asado
):
    registrar_venta(usuario, [(aceite.pk, Decimal("3")), (asado.pk, Decimal("0.750"))], efectivo)

    aceite.refresh_from_db()
    asado.refresh_from_db()
    assert aceite.stock_actual == Decimal("7")
    assert asado.stock_actual == Decimal("0")


def test_dec53_un_producto_repetido_suma_en_una_linea(usuario, caja_hoy, efectivo, aceite):
    venta, _ = registrar_venta(
        usuario, [(aceite.pk, Decimal("1")), (aceite.pk, Decimal("2"))], efectivo
    )

    detalle = venta.detalleventa_set.get()
    assert detalle.cantidad == Decimal("3") and detalle.subtotal == Decimal("7500.00")


def test_dec49_el_subtotal_se_redondea_a_centavos():
    assert subtotal(Decimal("0.333"), Decimal("10.00")) == Decimal("3.33")
    assert subtotal(Decimal("0.125"), Decimal("1.00")) == Decimal("0.13")


# CP-14 (RNF-10)


def test_cp14_si_falla_la_caja_no_queda_nada(usuario, caja_hoy, efectivo, aceite):
    with (
        mock.patch(
            "apps.ventas.services.registrar_ingreso_venta", side_effect=RuntimeError("falla")
        ),
        pytest.raises(RuntimeError),
    ):
        registrar_venta(usuario, [(aceite.pk, Decimal("2"))], efectivo)

    aceite.refresh_from_db()
    assert _nada_guardado()
    assert aceite.stock_actual == Decimal("10")


# CP-15 (RI-12)


def test_cp15_cambiar_el_precio_no_cambia_la_venta(usuario, caja_hoy, efectivo, aceite):
    venta, _ = registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)
    aceite.precio_venta = Decimal("9999.00")
    aceite.save()

    venta.refresh_from_db()
    assert venta.detalleventa_set.get().precio_unitario == Decimal("2500.00")
    assert venta.monto_total == Decimal("2500.00")


# CP-16 (RI-16, DEC-48)


@pytest.mark.parametrize("cantidad", [Decimal("0"), Decimal("-1")])
def test_cp16_cantidad_no_positiva_se_rechaza(usuario, caja_hoy, efectivo, aceite, cantidad):
    with pytest.raises(ValidationError, match="tiene que ser mayor a 0"):
        registrar_venta(usuario, [(aceite.pk, cantidad)], efectivo)
    assert _nada_guardado()


def test_dec48_por_unidad_solo_cantidades_enteras(usuario, caja_hoy, efectivo, aceite):
    with pytest.raises(ValidationError, match="se vende por unidad"):
        registrar_venta(usuario, [(aceite.pk, Decimal("1.5"))], efectivo)


def test_dec48_por_kg_hasta_tres_decimales(usuario, caja_hoy, efectivo, asado):
    with pytest.raises(ValidationError, match="hasta 3 decimales"):
        registrar_venta(usuario, [(asado.pk, Decimal("1.2505"))], efectivo)


def test_dec76_hasta_el_maximo_por_linea_se_acepta(usuario, caja_hoy, efectivo, aceite, asado):
    venta, _ = registrar_venta(
        usuario, [(aceite.pk, Decimal("100")), (asado.pk, Decimal("100.000"))], efectivo
    )

    assert venta.detalleventa_set.count() == 2


@pytest.mark.parametrize(
    ("nombre", "cantidad", "unidad"),
    [
        ("asado", Decimal("1601"), "kg"),
        ("asado", Decimal("100.001"), "kg"),
        ("aceite", Decimal("101"), "unidades"),
    ],
)
def test_df01_dec76_cantidad_sobre_el_maximo_se_rechaza(
    request, usuario, caja_hoy, efectivo, nombre, cantidad, unidad
):
    producto = request.getfixturevalue(nombre)

    with pytest.raises(ValidationError, match=f"supera el máximo de 100 {unidad} por línea"):
        registrar_venta(usuario, [(producto.pk, cantidad)], efectivo)
    assert _nada_guardado()


def test_dec76_el_maximo_se_aplica_a_la_linea_agrupada(usuario, caja_hoy, efectivo, aceite):
    # DEC-53: un producto repetido es una sola línea.
    with pytest.raises(ValidationError, match="supera el máximo"):
        registrar_venta(usuario, [(aceite.pk, Decimal("60")), (aceite.pk, Decimal("41"))], efectivo)
    assert _nada_guardado()


def test_producto_inactivo_o_inexistente_se_rechaza(usuario, caja_hoy, efectivo, aceite):
    aceite.activo = False
    aceite.save()

    with pytest.raises(ValidationError, match="ya no está disponible"):
        registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)
    with pytest.raises(ValidationError, match="ya no está disponible"):
        registrar_venta(usuario, [(999999, Decimal("1"))], efectivo)
    assert _nada_guardado()


def test_venta_sin_productos_se_rechaza(usuario, caja_hoy, efectivo):
    with pytest.raises(ValidationError, match="no tiene productos"):
        registrar_venta(usuario, [], efectivo)


def test_venta_con_total_cero_se_rechaza(usuario, caja_hoy, efectivo, aceite):
    aceite.precio_venta = Decimal("0")
    aceite.save()

    with pytest.raises(ValidationError, match="tiene que ser mayor a 0"):
        registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)
    assert _nada_guardado()


# CP-21 y DEC-41: un medio de pago, sin cuenta corriente ni inactivos


def test_dec41_cuenta_corriente_e_inactivos_no_se_ofrecen_ni_se_aceptan(
    usuario, caja_hoy, efectivo, cuenta_corriente, aceite
):
    tarjeta = MedioPago.objects.create(nombre="Tarjeta", activo=False)

    assert list(medios_de_pago_para_venta()) == [efectivo]
    for medio in (cuenta_corriente, tarjeta):
        with pytest.raises(ValidationError) as error:
            registrar_venta(usuario, [(aceite.pk, Decimal("1"))], medio)
        assert "medio_pago" in error.value.message_dict
    assert _nada_guardado()


def test_cp21_la_venta_guarda_un_solo_medio_de_pago(usuario, caja_hoy, efectivo, aceite):
    venta, _ = registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)

    assert venta.medio_pago == efectivo
    assert MovimientoCaja.objects.filter(venta=venta).count() == 1


# CP-17 y DEC-50: caja abierta y de hoy


def test_cp17_sin_caja_abierta_se_rechaza(usuario, efectivo, aceite):
    with pytest.raises(ValidationError, match="No hay una caja abierta"):
        registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)
    assert _nada_guardado()


def test_dec50_con_la_caja_de_otro_dia_no_se_vende(usuario, caja, efectivo, aceite):
    assert caja.fecha != timezone.localdate()

    with pytest.raises(ValidationError, match="es de otro día"):
        registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)
    assert _nada_guardado()


def test_ri02_una_caja_cerrada_no_recibe_la_venta(usuario, caja_hoy, efectivo, aceite):
    caja_hoy.estado = EstadoCaja.CERRADA
    caja_hoy.cerrada_en = timezone.now()
    caja_hoy.save()

    with pytest.raises(ValidationError, match="No hay una caja abierta"):
        registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)


# CP-83 (DEC-46)


def test_cp83_stock_insuficiente_se_vende_con_aviso(usuario, caja_hoy, efectivo, aceite):
    venta, avisos = registrar_venta(usuario, [(aceite.pk, Decimal("12"))], efectivo)

    aceite.refresh_from_db()
    assert venta.pk is not None
    assert aceite.stock_actual == Decimal("-2")
    assert avisos == [
        "Stock insuficiente de Aceite 1 l: la venta se registró y el stock quedó negativo. "
        "Avisale al administrador."
    ]


# CP-82 (DEC-37, DEC-52)


def test_cp82_buscar_por_codigo_exacto_y_por_nombre(aceite, asado):
    exacto, resultados = buscar_para_venta(" 501 ")
    assert exacto == aceite and resultados == [aceite]

    exacto, resultados = buscar_para_venta("asa")
    assert exacto is None and resultados == [asado]

    assert buscar_para_venta("") == (None, [])


def test_la_busqueda_no_trae_inactivos(aceite):
    aceite.activo = False
    aceite.save()

    assert buscar_para_venta("501") == (None, [])


# Permisos


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_solo_la_cajera_vende(rol, caja_hoy, efectivo, aceite):
    otro = Usuario.objects.create_user(
        username="otro", password="clave-de-prueba-123", nombre_completo="Otro", rol=rol
    )

    with pytest.raises(PermissionDenied):
        registrar_venta(otro, [(aceite.pk, Decimal("1"))], efectivo)
