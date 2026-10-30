"""CP-113: el flujo completo de H3 de punta a punta, por las pantallas y con dos roles.

Proveedor → ingreso a crédito → venta con aviso de stock → tarjeta "stock bajo" → pago en
efectivo → cierre de caja.
"""

import json
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.caja.models import CierreCajaDetalle, ConceptoMovimientoCaja, EstadoCaja, MovimientoCaja
from apps.catalogo.models import Producto
from apps.proveedores.models import IngresoMercaderia, Proveedor
from apps.proveedores.services import saldo_de_ingreso, saldo_de_proveedor
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db


def _usuario(username, rol):
    return Usuario.objects.create_user(
        username=username, password="clave-de-prueba-123", nombre_completo=username, rol=rol
    )


def test_cp113_flujo_completo_de_h3(client, efectivo, categoria):
    admin = _usuario("admin", Rol.ADMINISTRADOR)
    cajera = _usuario("cajera", Rol.CAJERA)

    # El Administrador da de alta el proveedor y el producto.
    client.force_login(admin)
    client.post(reverse("proveedores:nuevo"), {"nombre": "Distribuidora Sur"})
    proveedor = Proveedor.objects.get()
    client.post(
        reverse("catalogo:nuevo"),
        {
            "nombre": "Yerba 1 kg",
            "categoria": categoria.pk,
            "plus_interno": "700",
            "precio_venta": "2000",
            "unidad_medida": "UNIDAD",
            "controla_stock": "on",
            "stock_minimo": "3",
        },
    )
    producto = Producto.objects.get()

    # Ingreso a crédito: sube el stock y deja la deuda.
    respuesta = client.post(
        reverse("proveedores:ingreso_confirmar"),
        {
            "proveedor": proveedor.pk,
            "observacion": "Remito 1",
            "lineas": json.dumps([{"producto": producto.pk, "cantidad": "5", "precio": "1000"}]),
        },
    )
    assert "detalle" in respuesta.json()
    ingreso = IngresoMercaderia.objects.get()
    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("5")
    assert saldo_de_proveedor(proveedor) == Decimal("5000.00")
    assert client.get(reverse("inicio")).context["stock_bajo"] == 0

    # La cajera abre la caja y vende más de lo que hay: se avisa y no se bloquea.
    client.force_login(cajera)
    client.post(reverse("caja:caja"), {"turno": "MANANA", "monto_inicial": "10000"})
    encontrado = client.get(reverse("ventas:buscar"), {"q": "700"}).json()["exacto"]
    assert encontrado["stock"] == "5.000"  # con este dato avisa la pantalla (CP-110)
    respuesta = client.post(
        reverse("ventas:confirmar"),
        {
            "medio_pago": efectivo.pk,
            "lineas": json.dumps([{"producto": producto.pk, "cantidad": "6"}]),
        },
    )
    ticket = client.get(respuesta.json()["ticket"]).content.decode()
    assert "Stock insuficiente de Yerba 1 kg" in ticket
    producto.refresh_from_db()
    assert producto.stock_actual == Decimal("-1")

    # El Administrador ve la tarjeta, que lleva al listado filtrado, y paga en efectivo.
    client.force_login(admin)
    assert client.get(reverse("inicio")).context["stock_bajo"] == 1
    filtrado = client.get(reverse("catalogo:productos"), {"stock_bajo": "1"})
    assert [p.nombre for p in filtrado.context["pagina"]] == ["Yerba 1 kg"]
    respuesta = client.post(
        reverse("proveedores:pago_nuevo"),
        {"ingreso": ingreso.pk, "monto": "5000", "medio_pago": efectivo.pk},
    )
    assert respuesta.status_code == 302
    assert saldo_de_ingreso(ingreso) == 0 and saldo_de_proveedor(proveedor) == 0
    egreso = MovimientoCaja.objects.get(concepto=ConceptoMovimientoCaja.PAGO_PROVEEDOR)
    assert egreso.usuario == admin and egreso.caja.usuario == cajera

    # La cajera cierra: lo esperado es fondo + venta - pago, y el cierre lo explica.
    client.force_login(cajera)
    assert "Distribuidora Sur" in client.get(reverse("caja:cerrar")).content.decode()
    respuesta = client.post(reverse("caja:cerrar"), {f"contado_{efectivo.pk}": "17000"})
    assert respuesta.status_code == 302
    caja = egreso.caja
    caja.refresh_from_db()
    assert caja.estado == EstadoCaja.CERRADA
    assert CierreCajaDetalle.objects.get(caja=caja).monto_sistema == Decimal("17000.00")
    reporte = client.get(reverse("caja:cierre", args=[caja.pk])).content.decode()
    assert "Pagos a proveedores" in reporte and "Distribuidora Sur" in reporte
