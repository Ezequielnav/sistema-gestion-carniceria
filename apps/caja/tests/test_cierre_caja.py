"""Etapa 3 de H2: egresos "otros" (CP-81) y cierre de caja (CP-04 a CP-07)."""

from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.caja.models import (
    Caja,
    CierreCajaDetalle,
    ConceptoMovimientoCaja,
    EstadoCaja,
    MedioPago,
    MovimientoCaja,
    TipoMovimientoCaja,
    Turno,
)
from apps.caja.services import (
    abrir_caja,
    cerrar_caja,
    detalle_de_cierre,
    egresos_otros,
    registrar_egreso_otro,
    resumen_de_cierre,
)
from apps.catalogo.models import Producto, UnidadMedida
from apps.usuarios.models import Rol, Usuario
from apps.ventas.services import registrar_venta

pytestmark = pytest.mark.django_db


@pytest.fixture
def tarjeta(db):
    return MedioPago.objects.create(nombre="Tarjeta")


@pytest.fixture
def cuenta_corriente(db):
    return MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)


@pytest.fixture
def asado(categoria):
    return Producto.objects.create(
        nombre="Asado",
        categoria=categoria,
        precio_venta=Decimal("9800.00"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=False,
    )


@pytest.fixture
def caja_con_movimientos(usuario, efectivo, tarjeta, asado, producto):
    """Fondo $ 5.000, venta en efectivo $ 19.250, venta con tarjeta $ 4.500, retiro $ 2.000."""
    caja = abrir_caja(usuario, Turno.MANANA, Decimal("5000"))
    producto.precio_venta = Decimal("3500.00")
    producto.stock_actual = Decimal("10")
    producto.save()
    registrar_venta(usuario, [(asado.pk, Decimal("1.250")), (producto.pk, Decimal("2"))], efectivo)
    producto.precio_venta = Decimal("900.00")
    producto.save()
    registrar_venta(usuario, [(producto.pk, Decimal("5"))], tarjeta)
    registrar_egreso_otro(usuario, Decimal("2000"), "Retiro para el dueño")
    return caja


def _esperados(caja):
    return {medio.nombre: esperado for medio, esperado in resumen_de_cierre(caja)}


# Egresos "otros" (CP-81, DEC-43, DEC-57, RI-13)


def test_cp81_egreso_otro_en_efectivo_con_descripcion(usuario, efectivo):
    caja = abrir_caja(usuario, Turno.MANANA, Decimal("5000"))

    egreso = registrar_egreso_otro(usuario, Decimal("1500.50"), "  Bolsas  ")

    assert egreso.tipo == TipoMovimientoCaja.EGRESO
    assert egreso.concepto == ConceptoMovimientoCaja.OTRO
    assert egreso.medio_pago == efectivo and egreso.caja == caja
    assert egreso.venta is None and egreso.pago_cliente is None and egreso.pago_proveedor is None
    assert egreso.descripcion == "Bolsas" and egreso.usuario == usuario
    assert egresos_otros(caja) == [egreso]


@pytest.mark.parametrize(
    ("monto", "descripcion", "campo"),
    [
        (Decimal("100"), "  ", "descripcion"),
        (Decimal("0"), "Bolsas", "monto"),
        (Decimal("-5"), "Bolsas", "monto"),
        (None, "Bolsas", "monto"),
    ],
)
def test_cp81_egreso_invalido_se_rechaza(usuario, efectivo, monto, descripcion, campo):
    abrir_caja(usuario, Turno.MANANA, Decimal("5000"))

    with pytest.raises(ValidationError) as error:
        registrar_egreso_otro(usuario, monto, descripcion)

    assert campo in error.value.message_dict
    assert not MovimientoCaja.objects.exists()


def test_dec57_egreso_mayor_al_efectivo_disponible_se_rechaza(usuario, efectivo):
    abrir_caja(usuario, Turno.MANANA, Decimal("1000"))

    with pytest.raises(ValidationError) as error:
        registrar_egreso_otro(usuario, Decimal("1000.01"), "Retiro")

    assert error.value.message_dict == {
        "monto": ["En la caja hay $ 1000.00 en efectivo: no alcanza."]
    }
    registrar_egreso_otro(usuario, Decimal("1000"), "Retiro")


def test_egreso_sin_caja_abierta_se_rechaza(usuario, efectivo):
    with pytest.raises(ValidationError, match="No hay una caja abierta"):
        registrar_egreso_otro(usuario, Decimal("10"), "Bolsas")


def test_sin_medio_en_efectivo_avisa(usuario):
    abrir_caja(usuario, Turno.MANANA)

    with pytest.raises(ValidationError, match="marcado como efectivo"):
        registrar_egreso_otro(usuario, Decimal("10"), "Bolsas")


def test_dec55_un_solo_medio_en_efectivo(efectivo):
    with pytest.raises(IntegrityError), transaction.atomic():
        MedioPago.objects.create(nombre="Pesos", es_efectivo=True)


# Lo esperado por medio (CP-07, DEC-38, DEC-56)


def test_cp07_esperado_por_medio_con_fondo_ventas_y_egresos(caja_con_movimientos, cuenta_corriente):
    assert _esperados(caja_con_movimientos) == {
        "Efectivo": Decimal("22250.00"),
        "Tarjeta": Decimal("4500.00"),
    }


def test_dec56_aparecen_los_medios_sin_movimientos_y_los_inactivos_con_movimientos(
    caja_con_movimientos, tarjeta
):
    qr = MedioPago.objects.create(nombre="QR")
    tarjeta.activo = False
    tarjeta.save()

    esperados = _esperados(caja_con_movimientos)

    assert esperados["QR"] == Decimal("0") and qr.pk
    assert esperados["Tarjeta"] == Decimal("4500.00")


# Cierre (CP-04, CP-05, CP-06, RF-08, RI-10, DEC-40)


def _contados(caja, **cambios):
    contados = {medio.pk: esperado for medio, esperado in resumen_de_cierre(caja)}
    for nombre, monto in cambios.items():
        contados[MedioPago.objects.get(nombre=nombre).pk] = monto
    return contados


def test_cp04_cierre_sin_diferencias(usuario, caja_con_movimientos):
    caja = cerrar_caja(usuario, _contados(caja_con_movimientos))

    caja.refresh_from_db()
    assert caja.estado == EstadoCaja.CERRADA
    assert caja.cerrada_en is not None and caja.cerrada_por_usuario == usuario
    assert caja.observacion_cierre == ""
    detalle = {m.nombre: (e, c, d) for m, e, c, d in detalle_de_cierre(caja)}
    assert detalle["Efectivo"] == (Decimal("22250.00"), Decimal("22250.00"), Decimal("0"))
    assert detalle["Tarjeta"] == (Decimal("4500.00"), Decimal("4500.00"), Decimal("0"))
    # RI-10: la diferencia no se guarda.
    assert not hasattr(CierreCajaDetalle(), "diferencia")


def test_cp06_con_diferencia_no_cierra_sin_motivo(usuario, caja_con_movimientos):
    contados = _contados(caja_con_movimientos, Efectivo=Decimal("22000"))

    with pytest.raises(ValidationError) as error:
        cerrar_caja(usuario, contados, "  ")

    assert "observacion" in error.value.message_dict
    caja_con_movimientos.refresh_from_db()
    assert caja_con_movimientos.estado == EstadoCaja.ABIERTA
    assert not CierreCajaDetalle.objects.exists()


def test_cp06_con_diferencia_y_motivo_cierra_sin_autorizacion(usuario, caja_con_movimientos):
    caja = cerrar_caja(
        usuario,
        _contados(caja_con_movimientos, Efectivo=Decimal("22000")),
        "Faltan $ 250 de un vuelto mal dado",
    )

    detalle = {m.nombre: d for m, _, _, d in detalle_de_cierre(caja)}
    assert detalle["Efectivo"] == Decimal("-250.00")
    assert caja.observacion_cierre == "Faltan $ 250 de un vuelto mal dado"


def test_contado_faltante_o_negativo_se_rechaza(usuario, caja_con_movimientos, tarjeta):
    contados = _contados(caja_con_movimientos)
    del contados[tarjeta.pk]
    with pytest.raises(ValidationError) as error:
        cerrar_caja(usuario, contados)
    assert error.value.message_dict == {f"contado_{tarjeta.pk}": ["Falta lo contado en Tarjeta."]}

    with pytest.raises(ValidationError) as error:
        cerrar_caja(usuario, _contados(caja_con_movimientos, Tarjeta=Decimal("-1")))
    assert error.value.message_dict == {f"contado_{tarjeta.pk}": ["No puede ser negativo."]}


def test_cp05_una_caja_cerrada_no_recibe_ventas_ni_egresos(
    usuario, caja_con_movimientos, efectivo, asado
):
    cerrar_caja(usuario, _contados(caja_con_movimientos))
    movimientos = MovimientoCaja.objects.count()

    with pytest.raises(ValidationError, match="No hay una caja abierta"):
        registrar_venta(usuario, [(asado.pk, Decimal("1"))], efectivo)
    with pytest.raises(ValidationError, match="No hay una caja abierta"):
        registrar_egreso_otro(usuario, Decimal("10"), "Bolsas")
    assert MovimientoCaja.objects.count() == movimientos


def test_despues_del_cierre_se_abre_el_turno_siguiente(usuario, caja_con_movimientos):
    cerrar_caja(usuario, _contados(caja_con_movimientos))

    assert abrir_caja(usuario, Turno.TARDE).estado == EstadoCaja.ABIERTA


def test_dec50_se_cierra_una_caja_de_otro_dia(usuario, caja, efectivo):
    assert caja.fecha != timezone.localdate()

    cerrada = cerrar_caja(usuario, {efectivo.pk: Decimal("0")})

    assert cerrada.pk == caja.pk and cerrada.estado == EstadoCaja.CERRADA


def test_cerrar_sin_caja_abierta_se_rechaza(usuario):
    with pytest.raises(ValidationError, match="No hay una caja abierta"):
        cerrar_caja(usuario, {})


# Permisos


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.DUENIO])
def test_solo_la_cajera_cierra_y_registra_egresos(rol, usuario, efectivo):
    abrir_caja(usuario, Turno.MANANA, Decimal("100"))
    otro = Usuario.objects.create_user(
        username="otro", password="clave-de-prueba-123", nombre_completo="Otro", rol=rol
    )

    with pytest.raises(PermissionDenied):
        registrar_egreso_otro(otro, Decimal("10"), "Bolsas")
    with pytest.raises(PermissionDenied):
        cerrar_caja(otro, {efectivo.pk: Decimal("100")})
    assert Caja.objects.get().estado == EstadoCaja.ABIERTA
