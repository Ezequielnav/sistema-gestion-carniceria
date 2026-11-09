"""CP-60 a CP-62 y CP-129 a CP-132: CU-09 Generar reportes en pantalla (H5, etapa 3).

Usa el escenario fijo de datos.py (fixture `escenario` en conftest.py).
"""

import re
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from apps.reportes import services
from apps.reportes.tests.datos import D15, D16, usuario
from apps.usuarios.models import Rol

pytestmark = pytest.mark.django_db

URLS = [
    "reportes:ventas",
    "reportes:productos",
    "reportes:ingresos",
    "reportes:medios",
    "reportes:cierres",
]


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
    client.force_login(usuario("duenio", Rol.DUENIO))

    assert client.get(reverse(url), {"desde": D15, "hasta": D16}).status_code == 200
    assert client.post(reverse(url)).status_code == 405


@pytest.mark.parametrize("url", ["reportes:inicio", *URLS])
def test_rf45_la_cajera_no_ve_reportes(client, url):
    cajera = usuario("cajera", Rol.CAJERA)
    client.force_login(cajera)

    assert client.get(reverse(url)).status_code == 403
    with pytest.raises(PermissionDenied):
        services.ventas_diarias(cajera, D15, D16)


def test_el_inicio_de_reportes_abre_el_resumen_con_el_rango(client, admin):
    client.force_login(admin)

    respuesta = client.get(
        reverse("reportes:inicio"), {"desde": "2026-01-15", "hasta": "2026-01-16"}
    )

    assert respuesta.url == reverse("reportes:resumen") + "?desde=2026-01-15&hasta=2026-01-16"


def test_con_un_rango_invalido_no_se_ofrece_exportar(client, admin):
    client.force_login(admin)

    respuesta = client.get(
        reverse("reportes:ventas"), {"desde": "2026-01-16", "hasta": "2026-01-15"}
    )

    assert "formato=excel" not in respuesta.content.decode()


# H7: Ventas diarias en pantalla, agrupadas por día


def test_h7_ventas_diarias_en_pantalla_agrupa_por_dia(client, admin, escenario):
    client.force_login(admin)

    html = client.get(
        reverse("reportes:ventas"), {"desde": D15.isoformat(), "hasta": D16.isoformat()}
    ).content.decode()
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))

    # El 15 tiene dos turnos: el día con su total y los turnos debajo.
    assert "Jue 15/01/2026 3 $ 1.800,00 Mañana 2 $ 1.500,00 Tarde 1 $ 300,00" in texto
    # El 16 tiene un turno: se nombra en la fila del día, sin fila aparte.
    assert "Vie 16/01/2026 Mañana 1 $ 700,00 Total del rango 4 $ 2.500,00" in texto
    assert "Total del día" not in texto


def test_h7_ingresos_por_dia_atenua_los_ceros(client, admin, escenario):
    """El 16 no tuvo cobros: su celda va atenuada; el total del día, no."""
    client.force_login(admin)

    html = client.get(
        reverse("reportes:ingresos"), {"desde": D15.isoformat(), "hasta": D16.isoformat()}
    ).content.decode()
    fila_16 = html.split("16/01/2026", 2)[2].split("</tr>", 1)[0]

    atenuadas = re.findall(r'<td class="[^"]*text-tinta-tenue[^"]*">([^<]*)</td>', fila_16)
    assert atenuadas and all(celda.strip() == "$ 0,00" for celda in atenuadas)
    assert "$ 700,00" in fila_16
