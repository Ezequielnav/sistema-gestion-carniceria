"""CP-60 a CP-62 y CP-129 a CP-132: CU-09 Generar reportes en pantalla (H5, etapa 3).

Un escenario fijo con dos cajas en la misma fecha y turno (DEC-83), una venta a cuenta
corriente, una venta anulada, cobros con caja y sin caja y un cobro anulado.
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import Caja, CierreCajaDetalle, EstadoCaja, MedioPago, Turno
from apps.catalogo.models import Producto, UnidadMedida
from apps.clientes.models import Cliente, EstadoPagoCliente, PagoCliente
from apps.reportes import services
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import DetalleVenta, EstadoVenta, Venta

pytestmark = pytest.mark.django_db

D15 = datetime.date(2026, 1, 15)
D16 = datetime.date(2026, 1, 16)
URLS = [
    "reportes:ventas",
    "reportes:productos",
    "reportes:ingresos",
    "reportes:medios",
    "reportes:cierres",
]


def _usuario(username, rol):
    return Usuario.objects.create_user(
        username=username, password="clave-de-prueba-123", nombre_completo=username, rol=rol
    )


def _caja(fecha, turno, cajera):
    return Caja.objects.create(
        fecha=fecha,
        turno=turno,
        usuario=cajera,
        estado=EstadoCaja.CERRADA,
        cerrada_en=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(14))),
        cerrada_por_usuario=cajera,
    )


def _venta(caja, medio, monto, renglones=(), anulada=False, cliente=None):
    venta = Venta.objects.create(
        caja=caja,
        usuario=caja.usuario,
        medio_pago=medio,
        monto_total=Decimal(monto),
        cliente=cliente,
    )
    for producto, cantidad, subtotal in renglones:
        DetalleVenta.objects.create(
            venta=venta,
            producto=producto,
            cantidad=Decimal(cantidad),
            precio_unitario=Decimal(subtotal) / Decimal(cantidad),
            subtotal=Decimal(subtotal),
        )
    if anulada:
        Venta.objects.filter(pk=venta.pk).update(
            estado=EstadoVenta.ANULADA,
            anulada_en=timezone.now(),
            anulada_por_usuario=caja.usuario,
            motivo_anulacion="Error de carga",
        )
    return venta


def _cobro(fecha, medio, monto, entra_a_caja, usuario, cliente, anulado=False):
    cobro = PagoCliente.objects.create(
        cliente=cliente,
        monto=Decimal(monto),
        medio_pago=medio,
        usuario=usuario,
        entra_a_caja=entra_a_caja,
        fecha_hora=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(11))),
    )
    if anulado:
        PagoCliente.objects.filter(pk=cobro.pk).update(
            estado=EstadoPagoCliente.ANULADO,
            anulado_en=timezone.now(),
            anulado_por_usuario=usuario,
            motivo_anulacion="Error de carga",
        )
    return cobro


@pytest.fixture
def admin(db):
    return _usuario("admin", Rol.ADMINISTRADOR)


@pytest.fixture
def escenario(admin):
    cajera = _usuario("cajera", Rol.CAJERA)
    efectivo = MedioPago.objects.create(nombre="Efectivo", es_efectivo=True)
    tarjeta = MedioPago.objects.create(nombre="Tarjeta")
    cuenta = MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)
    cliente = Cliente.objects.create(nombre="Cliente")
    asado = Producto.objects.create(
        nombre="Asado",
        precio_venta=Decimal("500"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=False,
    )
    yerba = Producto.objects.create(
        nombre="Yerba",
        precio_venta=Decimal("100"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=False,
    )
    # Dos cajas el 15 a la mañana (DEC-83), una a la tarde y una el 16.
    manana_1 = _caja(D15, Turno.MANANA, cajera)
    manana_2 = _caja(D15, Turno.MANANA, cajera)
    tarde = _caja(D15, Turno.TARDE, cajera)
    dia_16 = _caja(D16, Turno.MANANA, cajera)
    _venta(manana_1, efectivo, "1000", [(asado, "2", "1000")])
    _venta(manana_2, tarjeta, "500", [(yerba, "5", "500")])
    _venta(tarde, cuenta, "300", [(yerba, "3", "300")], cliente=cliente)
    _venta(tarde, efectivo, "200", [(asado, "0.4", "200")], anulada=True)
    _venta(dia_16, efectivo, "700", [(asado, "1.4", "700")])
    _cobro(D15, efectivo, "400", True, cajera, cliente)
    _cobro(D15, tarjeta, "250", False, admin, cliente)
    _cobro(D16, efectivo, "100", True, cajera, cliente, anulado=True)
    CierreCajaDetalle.objects.create(
        caja=manana_1,
        medio_pago=efectivo,
        monto_sistema=Decimal("1000"),
        monto_contado=Decimal("900"),
    )
    return {"manana_1": manana_1, "manana_2": manana_2, "tarde": tarde, "dia_16": dia_16}


# CP-60 (DEC-140): ventas diarias por fecha y turno


def test_cp60_ventas_diarias_suma_las_cajas_del_mismo_turno_sin_anuladas(admin, escenario):
    reporte = services.ventas_diarias(admin, D15, D16)

    dias = [(d["fecha"], d["cantidad"], d["total"]) for d in reporte["dias"]]
    assert dias == [(D15, 3, Decimal("1800.00")), (D16, 1, Decimal("700.00"))]
    turnos = [(t["turno"], t["cantidad"], t["total"]) for t in reporte["dias"][0]["turnos"]]
    assert turnos == [("Mañana", 2, Decimal("1500.00")), ("Tarde", 1, Decimal("300.00"))]
    assert (reporte["cantidad"], reporte["total"]) == (4, Decimal("2500.00"))


def test_cp60_el_rango_limita_por_la_fecha_de_la_caja(admin, escenario):
    reporte = services.ventas_diarias(admin, D16, D16)

    assert [d["fecha"] for d in reporte["dias"]] == [D16]
    assert reporte["total"] == Decimal("700.00")


# CP-129 (DEC-141): producto más vendido


def test_cp129_ranking_por_importe_con_la_cantidad_en_su_unidad(client, admin, escenario):
    reporte = services.productos_mas_vendidos(admin, D15, D16)

    filas = [(f["producto__nombre"], f["cantidad"], f["importe"]) for f in reporte["productos"]]
    assert filas == [
        ("Asado", Decimal("3.400"), Decimal("1700.00")),
        ("Yerba", Decimal("8.000"), Decimal("800.00")),
    ]
    assert reporte["total"] == Decimal("2500.00")
    client.force_login(admin)
    contenido = client.get(
        reverse("reportes:productos"), {"desde": D15, "hasta": D16}
    ).content.decode()
    assert "3,400 kg" in contenido


# CP-130 (DEC-142): ingresos por día


def test_cp130_ingresos_sin_cuenta_corriente_ni_anulados_y_separando_la_caja(admin, escenario):
    reporte = services.ingresos_por_dia(admin, D15, D16)

    dia_15, dia_16 = reporte["dias"]
    # Ventas: 1000 + 500 (la de cuenta corriente y la anulada no cuentan); cobros: 400 + 250.
    assert dia_15 == {
        "fecha": D15,
        "ventas": Decimal("1500.00"),
        "cobros": Decimal("650.00"),
        "en_caja": Decimal("1900.00"),
        "fuera": Decimal("250.00"),
        "total": Decimal("2150.00"),
    }
    # El cobro del 16 está anulado.
    assert (dia_16["cobros"], dia_16["total"]) == (Decimal("0.00"), Decimal("700.00"))
    assert reporte["totales"]["total"] == Decimal("2850.00")


# CP-61 (DEC-143): totales por medio de pago


def test_cp61_totales_por_medio_coinciden_con_las_ventas_diarias(admin, escenario):
    reporte = services.totales_por_medio(admin, D15, D16)

    filas = [(m["medio"], m["cantidad"], m["ventas"], m["cobros"]) for m in reporte["medios"]]
    assert filas == [
        ("Efectivo", 2, Decimal("1700.00"), Decimal("400.00")),
        ("Tarjeta", 1, Decimal("500.00"), Decimal("250.00")),
        ("Cuenta corriente", 1, Decimal("300.00"), Decimal("0.00")),
    ]
    assert reporte["totales"]["ventas"] == services.ventas_diarias(admin, D15, D16)["total"]
    assert reporte["totales"]["total"] == Decimal("3150.00")


# CP-131 (DEC-144): consulta de cierres por fecha


def test_cp131_cierres_del_rango_con_la_diferencia_y_el_enlace(client, admin, escenario):
    cajas = list(services.cierres(admin, D15, D15))

    assert cajas == [escenario["manana_1"], escenario["manana_2"], escenario["tarde"]]
    assert [c.diferencia for c in cajas] == [Decimal("-100.00"), Decimal("0.00"), Decimal("0.00")]
    client.force_login(admin)
    contenido = client.get(
        reverse("reportes:cierres"), {"desde": D15, "hasta": D15}
    ).content.decode()
    assert reverse("caja:cierre", args=[escenario["manana_1"].pk]) in contenido


# CP-62 (RF-44): sin datos


@pytest.mark.parametrize("url", URLS)
def test_cp62_sin_datos_muestra_sin_registros_disponibles(client, admin, url):
    client.force_login(admin)

    respuesta = client.get(reverse(url), {"desde": D15, "hasta": D16})

    assert respuesta.status_code == 200
    assert "Sin registros disponibles" in respuesta.content.decode()


# CP-132 (DEC-145, CU-09 A2): rango


def test_cp132_sin_rango_muestra_el_dia_de_hoy(client, admin):
    client.force_login(admin)

    form = client.get(reverse("reportes:ventas")).context["form"]

    assert form.is_valid()
    assert form.cleaned_data["desde"] == form.cleaned_data["hasta"] == timezone.localdate()


@pytest.mark.parametrize(
    ("rango", "campo"),
    [
        ({"desde": "2026-01-16", "hasta": "2026-01-15"}, "desde"),
        ({"desde": "2026-01-15", "hasta": "2999-01-01"}, "hasta"),
        ({"desde": "2026-01-15", "hasta": ""}, "hasta"),
    ],
)
def test_cp132_un_rango_invalido_pide_corregirlo_sin_calcular(
    client, admin, monkeypatch, rango, campo
):
    def no_llamar(*args, **kwargs):
        raise AssertionError("con un rango inválido no se calcula el reporte")

    monkeypatch.setattr("apps.reportes.views.services.ventas_diarias", no_llamar)
    client.force_login(admin)

    respuesta = client.get(reverse("reportes:ventas"), rango)

    assert respuesta.context["form"].errors[campo]
    assert "Corregí el rango de fechas" in respuesta.content.decode()


# RF-45 y DEC-134: el dueño consulta; la cajera no; nadie modifica


@pytest.mark.parametrize("url", URLS)
def test_rf45_el_duenio_consulta_los_reportes(client, escenario, url):
    client.force_login(_usuario("duenio", Rol.DUENIO))

    assert client.get(reverse(url), {"desde": D15, "hasta": D16}).status_code == 200
    assert client.post(reverse(url)).status_code == 405


@pytest.mark.parametrize("url", ["reportes:inicio", *URLS])
def test_rf45_la_cajera_no_ve_reportes(client, url):
    cajera = _usuario("cajera", Rol.CAJERA)
    client.force_login(cajera)

    assert client.get(reverse(url)).status_code == 403
    with pytest.raises(PermissionDenied):
        services.ventas_diarias(cajera, D15, D16)


def test_el_inicio_de_reportes_abre_ventas_diarias_con_el_rango(client, admin):
    client.force_login(admin)

    respuesta = client.get(
        reverse("reportes:inicio"), {"desde": "2026-01-15", "hasta": "2026-01-16"}
    )

    assert respuesta.url == reverse("reportes:ventas") + "?desde=2026-01-15&hasta=2026-01-16"
