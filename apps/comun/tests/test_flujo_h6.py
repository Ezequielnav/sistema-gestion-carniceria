"""CP-151: el flujo completo de H6 de punta a punta, por las pantallas.

La cajera abre la caja, vende, cobra una cuenta corriente y recibe el comprobante (DEC-185),
y cierra → abre la caja de la tarde → el Administrador anula el cobro de la mañana, con su
caja ya cerrada, y la reversa va en la caja de la tarde (DEC-166) → el estado de cuenta
muestra el saldo acumulado (DEC-168) → el dueño ve los reportes con su nota (DEC-186).
"""

import json
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import Caja, CierreCajaDetalle, ConceptoMovimientoCaja, MovimientoCaja, Turno
from apps.clientes.models import EstadoPagoCliente, PagoCliente
from apps.clientes.services import saldo
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db


def _entrar(username, rol):
    usuario = Usuario.objects.create_user(
        username=username,
        password="clave-de-prueba-123",
        nombre_completo=f"Persona {username}",
        rol=rol,
    )
    cliente = Client()
    cliente.force_login(usuario)
    return cliente


def test_cp151_flujo_completo_de_h6(efectivo, producto, cliente):
    hoy = timezone.localdate()
    oficina = _entrar("admin_h6", Rol.ADMINISTRADOR)
    mostrador = _entrar("cajera_h6", Rol.CAJERA)
    duenio = _entrar("duenio_h6", Rol.DUENIO)
    producto.stock_actual = Decimal("10")
    producto.save()

    # El Administrador carga la deuda que el cliente ya tenía (DEC-119).
    oficina.post(
        reverse("clientes:saldo_inicial", args=[cliente.pk]),
        {"monto": "1000", "fecha_origen": hoy.isoformat(), "motivo": "Libreta"},
    )
    assert saldo(cliente) == Decimal("1000.00")

    # Mañana: abrir, vender, cobrar con comprobante y cerrar.
    mostrador.post(reverse("caja:caja"), {"turno": "MANANA", "monto_inicial": "1000"})
    manana = Caja.objects.get(turno=Turno.MANANA)
    venta = mostrador.post(
        reverse("ventas:confirmar"),
        {
            "medio_pago": efectivo.pk,
            "lineas": json.dumps([{"producto": producto.pk, "cantidad": "2"}]),
        },
    ).json()
    assert "ticket" in venta
    cobrado = mostrador.post(
        reverse("clientes:cobrar"),
        {"cliente": cliente.pk, "monto": "300", "medio_pago": efectivo.pk},
        follow=True,
    )
    cobro = PagoCliente.objects.get()
    assert cobrado.redirect_chain[-1][0] == reverse("clientes:comprobante", args=[cobro.pk])
    comprobante = cobrado.content.decode()
    assert "Comprobante de cobro N.º" in comprobante
    assert "$ 1.000,00" in comprobante and "$ 700,00" in comprobante  # saldo anterior y posterior
    # 1.000 de fondo + 5.000 de la venta + 300 del cobro.
    cierre = mostrador.post(reverse("caja:cerrar"), {f"contado_{efectivo.pk}": "6300"})
    assert cierre.status_code == 302
    cierre_de_la_manana = list(CierreCajaDetalle.objects.filter(caja=manana).values())
    assert mostrador.get(reverse("clientes:comprobante", args=[cobro.pk])).status_code == 403

    # Tarde: el Administrador corrige el cobro con la caja de la mañana ya cerrada.
    mostrador.post(reverse("caja:caja"), {"turno": "TARDE", "monto_inicial": "500"})
    tarde = Caja.objects.get(turno=Turno.TARDE)
    detalle = oficina.get(reverse("clientes:cobro", args=[cobro.pk])).content.decode()
    assert "la reversa va en la caja abierta del" in detalle and "turno tarde" in detalle
    anulado = oficina.post(
        reverse("clientes:cobro_anular", args=[cobro.pk]), {"motivo": "Se cobró dos veces"}
    )
    assert anulado.status_code == 302
    cobro.refresh_from_db()
    assert cobro.estado == EstadoPagoCliente.ANULADO
    reversa = MovimientoCaja.objects.get(concepto=ConceptoMovimientoCaja.ANULACION_COBRO)
    assert reversa.caja == tarde
    assert list(CierreCajaDetalle.objects.filter(caja=manana).values()) == cierre_de_la_manana
    assert saldo(cliente) == Decimal("1000.00")

    # Estado de cuenta: el saldo acumulado vuelve a 1.000 después de la anulación.
    estado = oficina.get(reverse("clientes:estado", args=[cliente.pk]))
    assert [m.saldo_acumulado for m in estado.context["pagina"].object_list] == [
        Decimal("1000.00"),
        Decimal("700.00"),
        Decimal("1000.00"),
    ]

    # El cierre de la tarde lista la reversa con la fecha del cobro.
    a_cerrar = mostrador.get(reverse("caja:cerrar")).content.decode()
    assert f"cobro del {hoy:%d/%m/%Y}" in a_cerrar

    # Reportes: el cobro anulado no se cuenta; la nota lo explica (DEC-186).
    rango = {"desde": hoy.isoformat(), "hasta": hoy.isoformat()}
    ingresos = duenio.get(reverse("reportes:ingresos"), rango)
    assert ingresos.context["reporte"]["totales"]["cobros"] == Decimal("0")
    assert ingresos.context["reporte"]["totales"]["ventas"] == Decimal("5000.00")
    assert "Un cobro anulado no se cuenta, aunque su caja ya haya cerrado" in (
        ingresos.content.decode()
    )
    medios = duenio.get(reverse("reportes:medios"), rango).content.decode()
    assert "aunque su caja ya haya cerrado: el cierre de esa caja los conserva" in medios
    cierres = duenio.get(reverse("reportes:cierres"), rango)
    assert [caja.pk for caja in cierres.context["reporte"]["cajas"]] == [manana.pk]
