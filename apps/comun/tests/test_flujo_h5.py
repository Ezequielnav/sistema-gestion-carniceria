"""CP-134: el flujo completo de H5 de punta a punta, por las pantallas y con los tres roles.

El Administrador del negocio (sin panel) configura medios de pago y categorías y da de alta a
una cajera y a un dueño (CU-14) → la cajera ingresa con su contraseña, ve su inicio, vende y
cierra la caja → ingresos y pagos a proveedores con sus filtros → el dueño ve el Resumen y
los reportes y exporta → el Administrador desactiva a la cajera, que queda afuera.
"""

import io
import json
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.caja.models import Caja, EstadoCaja, MedioPago
from apps.catalogo.forms import ProductoForm
from apps.catalogo.models import Categoria
from apps.proveedores.models import CondicionPago, IngresoMercaderia, Proveedor
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

CLAVE = "clave-de-revision-2026"


def _alta(client, username, rol):
    respuesta = client.post(
        reverse("usuarios:nuevo"),
        {
            "username": username,
            "nombre_completo": f"Persona {username}",
            "telefono": "",
            "email": "",
            "rol": rol,
            "puede_crear_productos": "",
            "password1": CLAVE,
            "password2": CLAVE,
        },
    )
    assert respuesta.status_code == 302
    return Usuario.objects.get(username=username)


def _vender(client, producto, medio, cantidad):
    return client.post(
        reverse("ventas:confirmar"),
        {
            "medio_pago": medio.pk,
            "lineas": json.dumps([{"producto": producto.pk, "cantidad": cantidad}]),
        },
    ).json()


def test_cp134_flujo_completo_de_h5(client, efectivo, producto):
    hoy = timezone.localdate().isoformat()
    producto.stock_actual = Decimal("20")
    producto.save()  # $ 2.500 por unidad
    admin = Usuario.objects.create_user(
        username="admin_negocio", password=CLAVE, nombre_completo="Andrés", rol=Rol.ADMINISTRADOR
    )
    assert not admin.is_staff  # DEC-150

    # Configuración sin panel (DEC-155): un medio de pago y una categoría que se da de baja.
    client.force_login(admin)
    client.post(reverse("caja:medio_nuevo"), {"nombre": "Tarjeta", "ingresa_a_caja": "on"})
    tarjeta = MedioPago.objects.get(nombre="Tarjeta")
    client.post(reverse("catalogo:categoria_nueva"), {"nombre": "Bebidas"})
    bebidas = Categoria.objects.get(nombre="Bebidas")
    client.post(reverse("catalogo:categoria_baja", args=[bebidas.pk]))
    assert bebidas not in ProductoForm().fields["categoria"].queryset
    assert client.get(reverse("admin:index")).status_code == 302  # no entra al panel

    # CU-14: alta de una cajera y de un dueño, que ingresan con su contraseña.
    cajera = _alta(client, "marta", Rol.CAJERA)
    _alta(client, "daniel", Rol.DUENIO)
    mostrador = Client()
    assert mostrador.login(username="marta", password=CLAVE)

    # La cajera ve su inicio sin totales (DEC-137), abre la caja, vende y cierra.
    inicio = mostrador.get(reverse("inicio"))
    assert [t.name for t in inicio.templates][0] == "comun/inicio_cajera.html"
    assert "Ventas de hoy" not in inicio.content.decode()
    mostrador.post(reverse("caja:caja"), {"turno": "MANANA", "monto_inicial": "0"})
    assert "ticket" in _vender(mostrador, producto, efectivo, "2")
    assert "ticket" in _vender(mostrador, producto, tarjeta, "1")
    mostrador.post(
        reverse("caja:cerrar"), {f"contado_{efectivo.pk}": "5000", f"contado_{tarjeta.pk}": "2500"}
    )
    caja = Caja.objects.get()
    assert caja.estado == EstadoCaja.CERRADA
    assert mostrador.get(reverse("reportes:ventas")).status_code == 403

    # Ingresos y pagos a proveedores, con sus filtros (DEC-152).
    proveedor = Proveedor.objects.create(nombre="Frigorífico Sur")
    otro = Proveedor.objects.create(nombre="Distribuidora Norte")
    for de_quien in (proveedor, otro):
        IngresoMercaderia.objects.create(
            fecha=timezone.localdate(),
            proveedor=de_quien,
            usuario=admin,
            total=Decimal("4000"),
            condicion_pago=CondicionPago.A_CREDITO,
        )
    filtrados = client.get(
        reverse("proveedores:ingresos"), {"proveedor": proveedor.pk, "desde": hoy}
    )
    assert [i.proveedor for i in filtrados.context["pagina"].object_list] == [proveedor]

    # El dueño: inicio con el acceso a Reportes, Resumen por defecto y reportes que coinciden.
    oficina = Client()
    assert oficina.login(username="daniel", password=CLAVE)
    assert [f.nombre for f in oficina.get(reverse("inicio")).context["menu"]] == ["Reportes"]
    resumen = oficina.get(reverse("reportes:inicio"), follow=True)
    assert resumen.redirect_chain[-1][0] == reverse("reportes:resumen")
    datos = resumen.context["reporte"]
    assert datos["ventas"] == {"cantidad": 2, "total": Decimal("7500.00")}
    assert datos["deuda_proveedores"] == Decimal("8000.00")
    ventas = oficina.get(reverse("reportes:ventas"), {"desde": hoy, "hasta": hoy})
    assert ventas.context["reporte"]["total"] == datos["ventas"]["total"]
    cierres = oficina.get(reverse("reportes:cierres"), {"desde": hoy, "hasta": hoy})
    assert cierres.context["reporte"]["cajas"] == [caja]
    excel = oficina.get(
        reverse("reportes:medios"), {"desde": hoy, "hasta": hoy, "formato": "excel"}
    )
    hoja = load_workbook(io.BytesIO(excel.content)).active
    filas = [f for f in hoja.iter_rows(min_row=7, values_only=True) if f[0]]
    assert ("Efectivo", 1, 5000, 0, 5000) in filas and ("Tarjeta", 1, 2500, 0, 2500) in filas
    pdf = oficina.get(reverse("reportes:ingresos"), {"desde": hoy, "hasta": hoy, "formato": "pdf"})
    assert pdf.content.startswith(b"%PDF")
    assert oficina.get(reverse("clientes:clientes")).status_code == 403

    # El Administrador desactiva a la cajera: su sesión se corta y no vuelve a ingresar.
    client.post(reverse("usuarios:baja", args=[cajera.pk]))
    assert mostrador.get(reverse("inicio")).status_code == 302
    assert not Client().login(username="marta", password=CLAVE)
    assert Usuario.objects.filter(pk=cajera.pk).exists()
