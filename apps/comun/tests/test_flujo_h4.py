"""CP-123: el flujo completo de H4 de punta a punta, por las pantallas y con dos roles.

Cliente con límite y saldo inicial → venta a cuenta corriente y una que pasa el límite →
cobro en la caja → anulaciones (venta rechazada por saldo, cobro, venta) → estado de cuenta
→ cierre de caja con el cobro y su reversa.
"""

import datetime
import json
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import (
    Caja,
    CierreCajaDetalle,
    ConceptoMovimientoCaja,
    EstadoCaja,
    MedioPago,
    MovimientoCaja,
)
from apps.clientes.models import Cliente, PagoCliente
from apps.clientes.services import saldo
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import EstadoVenta, Venta

pytestmark = pytest.mark.django_db


def _usuario(username, rol):
    return Usuario.objects.create_user(
        username=username, password="clave-de-prueba-123", nombre_completo=username, rol=rol
    )


def _vender(client, producto, medio, cliente, cantidad):
    return client.post(
        reverse("ventas:confirmar"),
        {
            "medio_pago": medio.pk,
            "lineas": json.dumps([{"producto": producto.pk, "cantidad": cantidad}]),
            "cliente": cliente.pk,
        },
    )


def test_cp123_flujo_completo_de_h4(client, efectivo, producto):
    admin = _usuario("admin", Rol.ADMINISTRADOR)
    cajera = _usuario("cajera", Rol.CAJERA)
    cuenta_corriente = MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)
    producto.stock_actual = Decimal("10")
    producto.save()  # $ 2.500 por unidad

    # El Administrador da de alta al cliente con límite y le carga la deuda que ya tenía.
    client.force_login(admin)
    client.post(
        reverse("clientes:nuevo"),
        {"nombre": "Juan Pérez", "telefono": "381 555-0101", "limite_credito": "10000"},
    )
    cliente = Cliente.objects.get()
    origen = timezone.localdate() - datetime.timedelta(days=40)
    client.post(
        reverse("clientes:saldo_inicial", args=[cliente.pk]),
        {"monto": "2000", "fecha_origen": origen.isoformat(), "motivo": "Libreta"},
    )
    assert saldo(cliente) == Decimal("2000.00")

    # La cajera abre la caja y vende a cuenta corriente; la segunda venta pasa el límite.
    client.force_login(cajera)
    client.post(reverse("caja:caja"), {"turno": "MANANA", "monto_inicial": "1000"})
    caja = Caja.objects.get()
    assert "ticket" in _vender(client, producto, cuenta_corriente, cliente, "2").json()
    venta = Venta.objects.get()
    assert saldo(cliente) == Decimal("7000.00")
    rechazada = _vender(client, producto, cuenta_corriente, cliente, "2")
    assert "supera el límite" in rechazada.json()["errores"][0]
    assert Venta.objects.count() == 1
    ticket = client.get(reverse("ventas:ticket", args=[venta.pk])).content.decode()
    assert "Cliente: Juan Pérez" in ticket

    # Cobra $ 3.000 en efectivo en la caja abierta.
    client.post(
        reverse("clientes:cobrar"),
        {"cliente": cliente.pk, "monto": "3000", "medio_pago": efectivo.pk},
    )
    cobro = PagoCliente.objects.get()
    assert cobro.entra_a_caja and saldo(cliente) == Decimal("4000.00")

    # El Administrador intenta anular la venta: el saldo ($ 4.000) no alcanza (DEC-114).
    client.force_login(admin)
    anular_venta = reverse("ventas:anular", args=[venta.pk])
    assert client.post(anular_venta, {"motivo": "Cliente equivocado"}).status_code == 400
    # Anula primero el cobro (con su reversa en la caja) y después la venta.
    client.post(reverse("clientes:cobro_anular", args=[cobro.pk]), {"motivo": "Se cobró de más"})
    assert saldo(cliente) == Decimal("7000.00")
    assert client.post(anular_venta, {"motivo": "Cliente equivocado"}).status_code == 302
    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.ANULADA and saldo(cliente) == Decimal("2000.00")
    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("10")

    # El estado de cuenta muestra todo y la alerta por el saldo inicial de hace 40 días.
    estado = client.get(reverse("clientes:estado", args=[cliente.pk]))
    html = estado.content.decode()
    assert estado.context["cliente"].deuda_vencida == Decimal("2000.00")
    assert "Tiene deuda vencida" in html
    assert len(estado.context["pagina"]) == 5  # saldo inicial, venta, cobro y sus anulaciones

    # La cajera cierra: el cobro y su reversa se compensan y la venta a cuenta no entra.
    client.force_login(cajera)
    assert "Cobros de cuenta corriente" in client.get(reverse("caja:cerrar")).content.decode()
    respuesta = client.post(reverse("caja:cerrar"), {f"contado_{efectivo.pk}": "1000"})
    caja.refresh_from_db()
    assert respuesta.url == reverse("caja:cierre", args=[caja.pk])
    assert caja.estado == EstadoCaja.CERRADA and caja.observacion_cierre == ""
    assert CierreCajaDetalle.objects.get(caja=caja).monto_sistema == Decimal("1000.00")
    assert set(MovimientoCaja.objects.values_list("concepto", flat=True)) == {
        ConceptoMovimientoCaja.PAGO_CLIENTE,
        ConceptoMovimientoCaja.ANULACION_COBRO,
    }
