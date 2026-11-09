"""CP-153 (DEC-186): los reportes cuentan los cobros vigentes por su fecha; los cierres, el
movimiento de caja. Con la corrección de L15 (DEC-166) la diferencia queda a la vista."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import CierreCajaDetalle, ConceptoMovimientoCaja, MovimientoCaja, Turno
from apps.caja.services import abrir_caja, cerrar_caja
from apps.clientes.models import MovimientoCuentaCorriente, TipoMovimientoCuentaCorriente
from apps.clientes.services import anular_cobro, registrar_cobro
from apps.proveedores.services import (
    anular_pago,
    registrar_ingreso,
    registrar_pago,
    saldos_de_proveedores,
)
from apps.reportes import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def corregidos(admin, usuario, efectivo, cliente, proveedor, producto):
    """A la mañana, un cobro de $ 300 y un pago a proveedor de $ 200 en efectivo; la caja se
    cierra y a la tarde el Administrador anula los dos, con la reversa en la caja abierta."""
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        tipo=TipoMovimientoCuentaCorriente.SALDO_INICIAL,
        monto=Decimal("1000.00"),
        fecha_origen=timezone.localdate(),
        motivo="Deuda anterior",
    )
    ingreso = registrar_ingreso(admin, proveedor, [(producto.pk, Decimal("1"), Decimal("500"))])
    manana = abrir_caja(usuario, Turno.MANANA, Decimal("1000.00"))
    cobro = registrar_cobro(usuario, cliente, Decimal("300"), efectivo)
    pago = registrar_pago(admin, ingreso, Decimal("200"), efectivo)
    cerrar_caja(usuario, {efectivo.pk: Decimal("1100.00")})
    cierre = list(CierreCajaDetalle.objects.filter(caja=manana).values("monto_sistema"))
    tarde = abrir_caja(usuario, Turno.TARDE, Decimal("500.00"))
    anular_cobro(admin, cobro, "Se cobró dos veces")
    anular_pago(admin, pago, "Se pagó dos veces")
    return manana, tarde, cierre


def test_cp153_los_reportes_no_cuentan_el_cobro_anulado_en_su_dia(admin, corregidos):
    hoy = timezone.localdate()

    ingresos = services.ingresos_por_dia(admin, hoy, hoy)
    medios = services.totales_por_medio(admin, hoy, hoy)

    assert ingresos["totales"]["cobros"] == Decimal("0")
    assert medios["totales"]["cobros"] == Decimal("0")


def test_cp153_el_cierre_de_la_caja_cerrada_no_cambia_y_la_reversa_va_en_la_otra(corregidos):
    manana, tarde, cierre = corregidos

    assert list(CierreCajaDetalle.objects.filter(caja=manana).values("monto_sistema")) == cierre
    assert cierre == [{"monto_sistema": Decimal("1100.00")}]
    assert set(
        MovimientoCaja.objects.filter(
            concepto__in=[
                ConceptoMovimientoCaja.ANULACION_COBRO,
                ConceptoMovimientoCaja.ANULACION_PAGO,
            ]
        ).values_list("caja_id", flat=True)
    ) == {tarde.pk}


def test_cp153_el_pago_anulado_vuelve_a_la_deuda_con_el_proveedor(proveedor, corregidos):
    assert saldos_de_proveedores([proveedor]) == {proveedor.pk: Decimal("500.00")}


def test_cp153_las_pantallas_explican_que_cuentan(client, admin, cliente, efectivo, corregidos):
    # Un cobro vigente para que los reportes tengan filas y muestren su nota.
    registrar_cobro(admin, cliente, Decimal("100"), efectivo, entra_a_caja=False)
    client.force_login(admin)

    ingresos = client.get(reverse("reportes:ingresos")).content.decode()
    medios = client.get(reverse("reportes:medios")).content.decode()

    assert "Un cobro anulado no se cuenta, aunque su caja ya haya cerrado" in ingresos
    assert "aunque su caja ya haya cerrado: el cierre de esa caja los conserva" in medios
    assert "$ 100,00" in ingresos and "$ 300,00" not in ingresos
