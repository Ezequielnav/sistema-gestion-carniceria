"""CP-138 a CP-140: pestaña "Resumen" de Reportes (RF-55, DEC-158).

Usa el escenario fijo de datos.py con el rango del 18/12/2025 al 16/01/2026, que abarca todas
las ventas y cobros del escenario.
"""

import datetime
import json
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from apps.catalogo.models import Producto, UnidadMedida
from apps.clientes.services import cargar_saldo_inicial
from apps.proveedores.models import CondicionPago, IngresoMercaderia, PagoProveedor, Proveedor
from apps.reportes import services
from apps.reportes.tablero import tablero
from apps.reportes.tests.datos import D15, D16, usuario
from apps.usuarios.models import Rol

pytestmark = pytest.mark.django_db

DESDE = D16 - datetime.timedelta(days=29)
RANGO = {"desde": DESDE.isoformat(), "hasta": D16.isoformat()}


@pytest.fixture
def completo(admin, escenario):
    """El escenario más una deuda vieja de cliente, una deuda con proveedor y stock bajo."""
    cargar_saldo_inicial(
        admin,
        escenario["cliente"],
        Decimal("800"),
        D15 - datetime.timedelta(days=40),
        "Deuda previa",
    )
    proveedor = Proveedor.objects.create(nombre="Frigorífico Sur")
    IngresoMercaderia.objects.create(
        fecha=D15,
        proveedor=proveedor,
        usuario=admin,
        total=Decimal("5000"),
        condicion_pago=CondicionPago.A_CREDITO,
    )
    PagoProveedor.objects.create(
        proveedor=proveedor, monto=Decimal("1000"), medio_pago=escenario["efectivo"], usuario=admin
    )
    Producto.objects.create(
        nombre="Fideos",
        precio_venta=Decimal("900"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=True,
        stock_actual=Decimal("0"),
    )
    return escenario


# CP-138: los números del Resumen son los de las otras pestañas y los servicios


def test_cp138_ventas_e_ingresos_iguales_a_los_reportes(admin, completo):
    datos = tablero(admin, DESDE, D16)

    del_rango = services.ventas_diarias(admin, DESDE, D16)
    assert datos["ventas"] == {"cantidad": del_rango["cantidad"], "total": del_rango["total"]}
    assert datos["ventas"] == {"cantidad": 4, "total": Decimal("2500.00")}
    assert datos["ticket_promedio"] == Decimal("625.00")
    assert datos["ingresos"] == services.ingresos_por_dia(admin, DESDE, D16)["totales"]
    assert datos["ingresos"]["fuera"] == Decimal("250.00")
    # Con un rango de un solo día, todo es de ese día.
    assert tablero(admin, D16, D16)["ventas"] == {"cantidad": 1, "total": Decimal("700.00")}


def test_cp138_graficos_iguales_a_los_reportes(admin, completo):
    datos = tablero(admin, DESDE, D16)

    assert len(datos["serie"]) == 30
    assert datos["serie"][0] == (DESDE, Decimal("0.00"))
    assert dict(datos["serie"])[D15] == Decimal("1800.00")
    assert sum(total for _, total in datos["serie"]) == Decimal("2500.00")
    assert len(tablero(admin, D15, D16)["serie"]) == 2
    medios = services.totales_por_medio(admin, DESDE, D16)["medios"]
    assert [(m["medio"], m["ventas"]) for m in datos["medios"]] == [
        (m["medio"], m["ventas"]) for m in medios
    ]
    ranking = list(services.productos_mas_vendidos(admin, DESDE, D16)["productos"])
    assert datos["top"] == ranking[:5]


def test_cp138_cuentas_corrientes_stock_y_proveedores_al_dia_de_hoy(admin, completo):
    datos = tablero(admin, D16, D16)

    # Saldo inicial de 800 con origen hace más de 30 días: todo vencido (DEC-109, DEC-119).
    assert datos["cuentas_corrientes"] == {"saldo": Decimal("800.00"), "vencida": Decimal("800.00")}
    assert datos["stock_bajo"] == 1
    assert datos["deuda_proveedores"] == Decimal("4000.00")


def test_cp138_la_pantalla_muestra_los_numeros_y_enlaza_con_el_rango(client, admin, completo):
    client.force_login(admin)

    respuesta = client.get(reverse("reportes:resumen"), RANGO)
    contenido = respuesta.content.decode()

    assert respuesta.context["reporte"] == tablero(admin, DESDE, D16)
    for monto in ("$ 2.500,00", "$ 625,00", "$ 800,00", "$ 4.000,00"):
        assert monto in contenido
    rango = "desde=2025-12-18&amp;hasta=2026-01-16"
    for url in ("reportes:ventas", "reportes:ingresos", "reportes:medios", "reportes:productos"):
        assert f"{reverse(url)}?{rango}" in contenido
    graficos = json.loads(
        contenido.split('id="datos-tablero" type="application/json">')[1].split("</script>")[0]
    )
    assert graficos["serie"]["etiquetas"][0] == "18/12"
    assert graficos["top"]["etiquetas"] == ["Asado", "Yerba"]
    assert "vendor/chart.js/chart-4.4.9.umd.js" in contenido
    # El Resumen no se exporta (DEC-158).
    assert "formato=excel" not in contenido
    archivo = client.get(reverse("reportes:resumen"), {**RANGO, "formato": "excel"})
    assert archivo["Content-Type"].startswith("text/html")


def test_cp138_abre_por_defecto_con_los_ultimos_30_dias(client, admin):
    client.force_login(admin)

    form = client.get(reverse("reportes:resumen")).context["form"]

    hoy = timezone.localdate()
    assert form.cleaned_data["hasta"] == hoy
    assert form.cleaned_data["desde"] == hoy - datetime.timedelta(days=29)
    assert client.get(reverse("reportes:inicio")).url == reverse("reportes:resumen")
    # Las demás pestañas siguen abriendo con el día de hoy.
    ventas = client.get(reverse("reportes:ventas")).context["form"]
    assert ventas.cleaned_data["desde"] == hoy


# CP-139: quién ve el Resumen


def test_cp139_el_administrador_ve_enlaces_a_sus_pantallas(client, admin, completo):
    client.force_login(admin)

    contenido = client.get(reverse("reportes:resumen"), RANGO).content.decode()

    for url in ("clientes:clientes", "catalogo:productos", "proveedores:proveedores"):
        assert f'href="{reverse(url)}' in contenido


def test_cp139_el_duenio_ve_los_totales_sin_enlaces_a_pantallas_que_no_son_suyas(client, completo):
    client.force_login(usuario("duenio", Rol.DUENIO))

    respuesta = client.get(reverse("reportes:resumen"), RANGO)
    contenido = respuesta.content.decode()

    assert respuesta.context["reporte"]["ventas"]["total"] == Decimal("2500.00")
    assert "$ 800,00" in contenido  # el total de cuentas corrientes, sin nombres
    assert "Cliente" not in contenido.split("Cuentas corrientes")[1].split("</div>")[0]
    for url in ("clientes:clientes", "catalogo:productos", "proveedores:proveedores"):
        assert f'href="{reverse(url)}' not in contenido


def test_cp139_la_cajera_no_ve_el_resumen(client, completo):
    cajera = usuario("otra_cajera", Rol.CAJERA)
    client.force_login(cajera)

    assert client.get(reverse("reportes:resumen")).status_code == 403
    with pytest.raises(PermissionDenied):
        tablero(cajera, DESDE, D16)


def test_cp139_es_de_solo_lectura_y_el_inicio_no_cambia(client, admin):
    client.force_login(admin)

    assert client.post(reverse("reportes:resumen")).status_code == 405
    inicio = client.get(reverse("inicio"))
    assert [t.name for t in inicio.templates][0] == "comun/inicio.html"
    assert "graficos" not in inicio.context


# CP-140: sin datos y rango inválido


def test_cp140_sin_datos_cada_bloque_lo_avisa(client, admin):
    client.force_login(admin)

    respuesta = client.get(reverse("reportes:resumen"), RANGO)
    contenido = respuesta.content.decode()

    # Vendido, ventas por día, ingresos, cuentas corrientes, stock bajo, proveedores, medios
    # de pago y productos más vendidos.
    assert contenido.count("Sin registros disponibles") == 8
    assert "<canvas" not in contenido
    assert respuesta.context["reporte"]["ticket_promedio"] is None


def test_cp140_con_un_rango_invalido_pide_corregirlo(client, admin):
    client.force_login(admin)

    respuesta = client.get(
        reverse("reportes:resumen"), {"desde": "2026-01-16", "hasta": "2026-01-15"}
    )

    assert respuesta.context["form"].errors["desde"]
    assert "Corregí el rango de fechas" in respuesta.content.decode()
    assert "<canvas" not in respuesta.content.decode()
