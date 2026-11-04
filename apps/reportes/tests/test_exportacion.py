"""CP-63: exportar los reportes de CU-09 a Excel y PDF (RF-43; DEC-146, H5 etapa 4).

El archivo tiene el mismo rango y los mismos datos que la pantalla (R-3); sin datos no hay
archivo (RF-44).
"""

import io
from decimal import Decimal

import pytest
from django.urls import reverse
from openpyxl import load_workbook
from reportlab import rl_config

from apps.catalogo.models import Producto, UnidadMedida
from apps.reportes import services
from apps.reportes.tests.datos import D15, D16, usuario, venta
from apps.usuarios.models import Rol

pytestmark = pytest.mark.django_db

RANGO = {"desde": D15.isoformat(), "hasta": D16.isoformat()}
EXPORTABLES = ["reportes:ventas", "reportes:productos", "reportes:ingresos", "reportes:medios"]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _excel(client, url, **rango):
    respuesta = client.get(reverse(url), {**(rango or RANGO), "formato": "excel"})
    assert respuesta["Content-Type"] == XLSX
    return respuesta, load_workbook(io.BytesIO(respuesta.content)).active


def _filas(hoja):
    """Las filas de la tabla, desde los encabezados (fila 6) hasta antes de la nota."""
    return [
        tuple(fila)
        for fila in hoja.iter_rows(min_row=6, values_only=True)
        if any(v is not None for v in fila)
    ]


@pytest.fixture
def cliente_admin(client, admin):
    client.force_login(admin)
    return client


# CP-63: Excel


def test_cp63_excel_de_ventas_diarias_con_los_datos_de_la_pantalla(cliente_admin, escenario):
    respuesta, hoja = _excel(cliente_admin, "reportes:ventas")

    assert respuesta["Content-Disposition"] == (
        'attachment; filename="ventas-diarias_2026-01-15_2026-01-16.xlsx"'
    )
    assert [hoja["A1"].value, hoja["A2"].value, hoja["A3"].value] == [
        "Carnicería Rojano",
        "Ventas diarias",
        "Del 15/01/2026 al 16/01/2026",
    ]
    filas = _filas(hoja)
    assert filas[0] == ("Fecha", "Turno", "Ventas", "Total")
    assert [f[1:] for f in filas[1:7]] == [
        ("Mañana", 2, 1500),
        ("Tarde", 1, 300),
        ("Total del día", 3, 1800),
        ("Mañana", 1, 700),
        ("Total del día", 1, 700),
        (None, 4, 2500),
    ]
    assert filas[6][0] == "Total del rango"
    # Montos como números con formato de pesos, para poder sumarlos (DEC-146).
    total = hoja.cell(row=6 + 6, column=4)
    assert total.value == 2500 and total.number_format == '"$" #,##0.00'


def test_cp63_excel_de_ingresos_con_la_columna_de_caja(cliente_admin, admin, escenario):
    _, hoja = _excel(cliente_admin, "reportes:ingresos")

    filas = _filas(hoja)
    assert filas[0][3:5] == ("Entró a caja", "Fuera de caja")
    pantalla = services.ingresos_por_dia(admin, D15, D16)
    total = filas[3]
    assert total[0] == "Total del rango"
    assert [Decimal(str(v)) for v in total[1:]] == [
        pantalla["totales"][c] for c in ("ventas", "cobros", "en_caja", "fuera", "total")
    ]


def test_cp63_excel_de_medios_y_productos_coincide_con_la_pantalla(cliente_admin, admin, escenario):
    _, medios = _excel(cliente_admin, "reportes:medios")
    filas = _filas(medios)
    assert [f[0] for f in filas[1:4]] == ["Efectivo", "Tarjeta", "Cuenta corriente"]
    assert (
        Decimal(str(filas[4][4])) == services.totales_por_medio(admin, D15, D16)["totales"]["total"]
    )

    _, productos = _excel(cliente_admin, "reportes:productos")
    asado = _filas(productos)[1]
    assert asado[:4] == (1, "Asado", 3.4, 1700)
    assert productos.cell(row=7, column=3).number_format == '0.000 "kg"'


def test_cp63_el_excel_de_productos_lleva_todo_el_ranking_no_solo_la_pagina(
    cliente_admin, escenario
):
    caja = escenario["dia_16"]
    efectivo = caja.venta_set.first().medio_pago
    productos = [
        Producto.objects.create(
            nombre=f"Producto {n:02}",
            precio_venta=Decimal("10"),
            unidad_medida=UnidadMedida.UNIDAD,
            controla_stock=False,
        )
        for n in range(30)
    ]
    venta(caja, efectivo, "300", [(p, "1", "10") for p in productos])

    pantalla = cliente_admin.get(reverse("reportes:productos"), RANGO)
    _, hoja = _excel(cliente_admin, "reportes:productos")

    assert len(pantalla.context["reporte"]["pagina"].object_list) == 25
    # Encabezado, 32 productos y el total.
    assert len(_filas(hoja)) == 1 + 32 + 1 + 1  # más la nota


# CP-63: PDF


@pytest.mark.parametrize("url", EXPORTABLES)
def test_cp63_pdf_de_cada_reporte(cliente_admin, escenario, url, monkeypatch):
    # Sin compresión, el texto del PDF se puede buscar en los bytes.
    monkeypatch.setattr(rl_config, "pageCompression", 0)

    respuesta = cliente_admin.get(reverse(url), {**RANGO, "formato": "pdf"})

    assert respuesta["Content-Type"] == "application/pdf"
    assert respuesta.content.startswith(b"%PDF")
    assert respuesta["Content-Disposition"].endswith('_2026-01-15_2026-01-16.pdf"')
    assert b"Del 15/01/2026 al 16/01/2026" in respuesta.content


def test_cp63_el_pdf_muestra_los_montos_como_la_pantalla(cliente_admin, escenario, monkeypatch):
    monkeypatch.setattr(rl_config, "pageCompression", 0)

    contenido = cliente_admin.get(reverse("reportes:ventas"), {**RANGO, "formato": "pdf"}).content

    for monto in (b"$ 1.500,00", b"$ 1.800,00", b"$ 2.500,00"):
        assert monto in contenido


# RF-44: sin datos no hay archivo


@pytest.mark.parametrize("formato", ["excel", "pdf"])
@pytest.mark.parametrize("url", EXPORTABLES)
def test_cp63_sin_datos_no_exporta_y_avisa(cliente_admin, url, formato):
    respuesta = cliente_admin.get(reverse(url), {**RANGO, "formato": formato})

    assert respuesta["Content-Type"].startswith("text/html")
    contenido = respuesta.content.decode()
    assert "Sin registros disponibles" in contenido
    assert "no hay nada para exportar" in contenido


def test_cp63_con_un_rango_invalido_no_exporta(cliente_admin, escenario):
    respuesta = cliente_admin.get(
        reverse("reportes:ventas"),
        {"desde": "2026-01-16", "hasta": "2026-01-15", "formato": "excel"},
    )

    assert respuesta["Content-Type"].startswith("text/html")
    assert respuesta.context["form"].errors


def test_cp63_la_consulta_de_cierres_no_se_exporta(cliente_admin, escenario):
    respuesta = cliente_admin.get(reverse("reportes:cierres"), {**RANGO, "formato": "excel"})

    assert respuesta["Content-Type"].startswith("text/html")
    assert "Exportar a Excel" not in respuesta.content.decode()


def test_cp63_las_pantallas_exportables_ofrecen_los_dos_formatos(cliente_admin, escenario):
    contenido = cliente_admin.get(reverse("reportes:ingresos"), RANGO).content.decode()

    assert "formato=excel" in contenido and "formato=pdf" in contenido


# RF-45: el dueño exporta; la cajera no


def test_cp63_el_duenio_exporta_y_la_cajera_no(client, escenario):
    client.force_login(usuario("duenio", Rol.DUENIO))
    _excel(client, "reportes:ventas")

    client.force_login(usuario("otra_cajera", Rol.CAJERA))
    assert client.get(reverse("reportes:ventas"), {**RANGO, "formato": "excel"}).status_code == 403
