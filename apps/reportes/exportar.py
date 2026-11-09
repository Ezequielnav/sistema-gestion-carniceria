"""Exportación de los reportes de CU-09 a Excel y PDF (RF-43; DEC-146, D-10).

Cada reporte se pasa a una `Tabla` armada con el mismo resultado del servicio que muestra la
pantalla (R-3, DEC-154): mismos datos, mismo rango y mismos totales. El Excel guarda montos y
cantidades como números para poder sumarlos; el PDF los muestra como en pantalla.
"""

import io
from dataclasses import dataclass, field

from django.utils import timezone
from django.utils.formats import date_format
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.catalogo.models import UnidadMedida, formatear_cantidad
from apps.comun.models import pesos
from apps.comun.templatetags.fechas import con_dia

NEGOCIO = "Carnicería Rojano"

# Tipos de columna: cómo se escribe cada valor en Excel y en el PDF.
TEXTO, FECHA, ENTERO, PESOS, CANTIDAD = "texto", "fecha", "entero", "pesos", "cantidad"
FORMATO_PESOS = '"$" #,##0.00'


@dataclass
class Tabla:
    titulo: str
    columnas: list  # [(encabezado, tipo)]
    # [(valores, estilo)]: estilo es True para un subtotal, o DIA y DETALLE en la tabla del PDF
    # agrupada por día (las filas de los turnos van debajo de su día).
    filas: list = field(default_factory=list)
    total: list | None = None
    nota: str = ""
    # En el PDF, los montos en cero en gris, para que se lean los reales (H7, ingresos por día).
    atenuar_ceros: bool = False


DIA, DETALLE = "dia", "detalle"


def _fila(valores, subtotal=False):
    return (valores, subtotal)


def tabla_ventas(reporte):
    """DEC-140: por fecha y turno de la caja, con el total de cada día."""
    tabla = Tabla(
        "Ventas diarias",
        [("Fecha", FECHA), ("Turno", TEXTO), ("Ventas", ENTERO), ("Total", PESOS)],
        nota="Sin las ventas anuladas. Incluye las ventas a cuenta corriente.",
    )
    for dia in reporte["dias"]:
        for turno in dia["turnos"]:
            tabla.filas.append(
                _fila([dia["fecha"], turno["turno"], turno["cantidad"], turno["total"]])
            )
        tabla.filas.append(
            _fila([dia["fecha"], "Total del día", dia["cantidad"], dia["total"]], True)
        )
    tabla.total = ["Total del rango", "", reporte["cantidad"], reporte["total"]]
    return tabla


def tabla_ventas_pdf(reporte):
    """Ventas diarias para el PDF, agrupadas por día (H7): una fila por día con sus ventas y
    su total; los turnos van debajo solo si el día tiene más de uno; con uno, se nombra en la
    fila del día. Mismos datos que `tabla_ventas`; el Excel sigue con esa, para trabajarla."""
    tabla = Tabla(
        "Ventas diarias",
        [("Fecha", TEXTO), ("Ventas", ENTERO), ("Total", PESOS)],
        nota="Sin las ventas anuladas. Incluye las ventas a cuenta corriente.",
    )
    for dia in reporte["dias"]:
        fecha = con_dia(dia["fecha"])
        if len(dia["turnos"]) == 1:
            fecha = f"{fecha} · {dia['turnos'][0]['turno']}"
        tabla.filas.append(((fecha, dia["cantidad"], dia["total"]), DIA))
        if len(dia["turnos"]) > 1:
            for turno in dia["turnos"]:
                tabla.filas.append(((turno["turno"], turno["cantidad"], turno["total"]), DETALLE))
    tabla.total = ["Total del rango", reporte["cantidad"], reporte["total"]]
    return tabla


def tabla_productos(reporte):
    """DEC-141: todos los productos del ranking, no solo la página que se ve."""
    tabla = Tabla(
        "Producto más vendido",
        [("#", ENTERO), ("Producto", TEXTO), ("Cantidad", CANTIDAD), ("Importe", PESOS)],
        nota="Ordenado por importe. Sin las ventas anuladas.",
    )
    for puesto, fila in enumerate(reporte["productos"], start=1):
        cantidad = (fila["cantidad"], fila["producto__unidad_medida"])
        tabla.filas.append(_fila([puesto, fila["producto__nombre"], cantidad, fila["importe"]]))
    tabla.total = ["", "Total vendido en el rango", None, reporte["total"]]
    return tabla


def tabla_ingresos(reporte):
    """DEC-142: con la columna que separa lo que entró a caja de lo que quedó fuera."""
    claves = ("ventas", "cobros", "en_caja", "fuera", "total")
    tabla = Tabla(
        "Ingresos por día",
        [
            ("Fecha", FECHA),
            ("Ventas", PESOS),
            ("Cobros de cuenta corriente", PESOS),
            ("Entró a caja", PESOS),
            ("Fuera de caja", PESOS),
            ("Total", PESOS),
        ],
        nota=(
            'Las ventas a cuenta corriente no son ingreso. "Fuera de caja" son los cobros '
            "registrados sin caja. No se restan egresos."
        ),
        atenuar_ceros=True,
    )
    for dia in reporte["dias"]:
        tabla.filas.append(_fila([dia["fecha"], *(dia[c] for c in claves)]))
    tabla.total = ["Total del rango", *(reporte["totales"][c] for c in claves)]
    return tabla


def tabla_medios(reporte):
    """DEC-143: ventas no anuladas y cobros vigentes por medio de pago."""
    tabla = Tabla(
        "Totales por medio de pago",
        [
            ("Medio de pago", TEXTO),
            ("Ventas", ENTERO),
            ("Monto de ventas", PESOS),
            ("Cobros", PESOS),
            ("Total", PESOS),
        ],
        nota="La cuenta corriente muestra lo vendido a cuenta, no dinero recibido.",
    )
    for medio in reporte["medios"]:
        tabla.filas.append(
            _fila(
                [
                    medio["medio"],
                    medio["cantidad"],
                    medio["ventas"],
                    medio["cobros"],
                    medio["total"],
                ]
            )
        )
    totales = reporte["totales"]
    tabla.total = [
        "Total",
        totales["cantidad"],
        totales["ventas"],
        totales["cobros"],
        totales["total"],
    ]
    return tabla


TABLAS = {
    "ventas": tabla_ventas,
    "productos": tabla_productos,
    "ingresos": tabla_ingresos,
    "medios": tabla_medios,
}
# El PDF se lee: Ventas diarias va agrupada por día. El Excel usa TABLAS, para trabajar los datos.
TABLAS_PDF = {**TABLAS, "ventas": tabla_ventas_pdf}


def nombre_de_archivo(nombre, desde, hasta, extension):
    return f"{nombre}_{desde.isoformat()}_{hasta.isoformat()}.{extension}"


def _encabezado(tabla, desde, hasta):
    rango = f"Del {date_format(desde, 'j/m/Y')} al {date_format(hasta, 'j/m/Y')}"
    generado = f"Generado el {date_format(timezone.localtime(), 'j/m/Y H:i')}"
    return [NEGOCIO, tabla.titulo, rango, generado]


# Excel


def excel(tabla, desde, hasta):
    """Libro .xlsx con montos y cantidades numéricos (DEC-146)."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = tabla.titulo[:31]
    for numero, texto in enumerate(_encabezado(tabla, desde, hasta), start=1):
        hoja.cell(row=numero, column=1, value=texto).font = Font(
            bold=numero <= 2, size=14 if numero == 1 else 11
        )
    fila_titulos = 6
    for columna, (titulo, tipo) in enumerate(tabla.columnas, start=1):
        celda = hoja.cell(row=fila_titulos, column=columna, value=titulo)
        celda.font = Font(bold=True)
        celda.fill = PatternFill("solid", fgColor="F3F4F6")
        if tipo not in (TEXTO, FECHA):
            celda.alignment = Alignment(horizontal="right")
    numero = fila_titulos
    for valores, subtotal in tabla.filas:
        numero += 1
        _escribir_fila(hoja, numero, tabla.columnas, valores, negrita=subtotal)
    if tabla.total:
        numero += 1
        _escribir_fila(hoja, numero, tabla.columnas, tabla.total, negrita=True)
    if tabla.nota:
        hoja.cell(row=numero + 2, column=1, value=tabla.nota).font = Font(italic=True)
    for columna, (titulo, _) in enumerate(tabla.columnas, start=1):
        letra = hoja.cell(row=fila_titulos, column=columna).column_letter
        hoja.column_dimensions[letra].width = max(14, len(titulo) + 4)
    hoja.freeze_panes = hoja.cell(row=fila_titulos + 1, column=1)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _escribir_fila(hoja, numero, columnas, valores, negrita=False):
    for columna, ((_, tipo), valor) in enumerate(zip(columnas, valores, strict=True), start=1):
        if valor is None or valor == "":
            continue
        if tipo == CANTIDAD:
            cantidad, unidad = valor
            celda = hoja.cell(row=numero, column=columna, value=cantidad)
            celda.number_format = '0.000 "kg"' if unidad == UnidadMedida.KG else "0"
        else:
            celda = hoja.cell(row=numero, column=columna, value=valor)
            if tipo == PESOS:
                celda.number_format = FORMATO_PESOS
            elif tipo == FECHA and not isinstance(valor, str):
                celda.number_format = "DD/MM/YYYY"
        celda.font = Font(bold=negrita)


# PDF


def _texto(tipo, valor):
    """Como en pantalla: "$ 1.234,56", "3,400 kg" y fechas con el día de la semana."""
    if valor is None or valor == "":
        return ""
    if tipo == PESOS:
        return pesos(valor)
    if tipo == CANTIDAD:
        return formatear_cantidad(*valor)
    if tipo == FECHA and not isinstance(valor, str):
        return con_dia(valor)
    return str(valor)


# S-10 (DEC-196): encabezado con la identidad del sistema, con las fuentes estándar de PDF
# (sin incrustar fuentes): el nombre en serif y una línea marino debajo.
MARINO = colors.HexColor("#0F2557")
TINTA = colors.HexColor("#211C17")
FONDO_ENCABEZADO = colors.HexColor("#EFE8DB")
LINEA = colors.HexColor("#CFC4B2")
TINTA_SUAVE = colors.HexColor("#625A50")
TINTA_TENUE = colors.HexColor("#8A8072")
# La tabla ocupa el ancho de la hoja: las columnas de números tienen ancho fijo y las de texto
# se reparten el resto.
ANCHO_UTIL = 180 * mm
ANCHOS_FIJOS = {PESOS: 28 * mm, ENTERO: 18 * mm, CANTIDAD: 26 * mm}


def _anchos(columnas):
    fijos = sum(ANCHOS_FIJOS.get(tipo, 0) for _, tipo in columnas)
    libres = [tipo for _, tipo in columnas if tipo not in ANCHOS_FIJOS]
    resto = (ANCHO_UTIL - fijos) / len(libres) if libres else 0
    return [ANCHOS_FIJOS.get(tipo, resto) for _, tipo in columnas]


def pdf(tabla, desde, hasta):
    """PDF A4 con el negocio, el reporte, el rango y la fecha de generación (DEC-146)."""
    estilos = getSampleStyleSheet()
    marca = ParagraphStyle(
        "Marca",
        parent=estilos["Title"],
        fontName="Times-Bold",
        fontSize=22,
        leading=26,
        textColor=MARINO,
        alignment=0,
        spaceAfter=2 * mm,
    )
    subtitulo = ParagraphStyle(
        "Reporte", parent=estilos["Heading2"], textColor=TINTA, spaceBefore=4 * mm
    )
    salida = io.BytesIO()
    documento = SimpleDocTemplate(
        salida,
        pagesize=A4,
        title=f"{tabla.titulo} - {NEGOCIO}",
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    negocio, titulo, rango, generado = _encabezado(tabla, desde, hasta)
    contenido = [
        Paragraph(negocio, marca),
        HRFlowable(width="100%", thickness=1.5, color=MARINO, spaceBefore=0, spaceAfter=0),
        Paragraph(titulo, subtitulo),
        Paragraph(f"{rango} · {generado}", estilos["Normal"]),
        Spacer(1, 6 * mm),
    ]
    # Encabezados como párrafos: uno largo ("Cobros de cuenta corriente") ocupa dos renglones
    # en lugar de pisar la columna de al lado.
    encabezado = ParagraphStyle("Encabezado", fontName="Helvetica-Bold", fontSize=9, leading=11)
    a_la_derecha = ParagraphStyle("EncabezadoDerecha", parent=encabezado, alignment=2)
    datos = [
        [
            Paragraph(titulo, encabezado if tipo in (TEXTO, FECHA) else a_la_derecha)
            for titulo, tipo in tabla.columnas
        ]
    ]
    resaltadas, dias, detalles = [], [], []
    for valores, estilo_fila in tabla.filas:
        datos.append(
            [_texto(tipo, v) for (_, tipo), v in zip(tabla.columnas, valores, strict=True)]
        )
        fila = len(datos) - 1
        if estilo_fila == DIA:
            dias.append(fila)
        elif estilo_fila == DETALLE:
            detalles.append(fila)
        elif estilo_fila:
            resaltadas.append(fila)
    total = None
    if tabla.total:
        datos.append(
            [_texto(tipo, v) for (_, tipo), v in zip(tabla.columnas, tabla.total, strict=True)]
        )
        total = len(datos) - 1
    ceros = []
    if tabla.atenuar_ceros:
        valores_por_fila = [valores for valores, _ in tabla.filas] + (
            [tabla.total] if tabla.total else []
        )
        for fila, valores in enumerate(valores_por_fila, start=1):
            for columna, ((_, tipo), valor) in enumerate(zip(tabla.columnas, valores, strict=True)):
                if tipo == PESOS and valor == 0:
                    ceros.append((columna, fila))
    estilo = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ("BACKGROUND", (0, 0), (-1, 0), FONDO_ENCABEZADO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINEA),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]
    for columna, (_, tipo) in enumerate(tabla.columnas):
        if tipo not in (TEXTO, FECHA):
            estilo.append(("ALIGN", (columna, 0), (columna, -1), "RIGHT"))
    for fila in resaltadas:
        estilo += [
            ("FONTNAME", (0, fila), (-1, fila), "Helvetica-Bold"),
            ("LINEABOVE", (0, fila), (-1, fila), 0.5, LINEA),
        ]
    # Agrupada por día: el día en negrita, separado del anterior; sus turnos, con sangría y
    # en gris, pegados a su día.
    for fila in dias:
        estilo.append(("FONTNAME", (0, fila), (-1, fila), "Helvetica-Bold"))
        if fila > 1:
            estilo.append(("LINEABOVE", (0, fila), (-1, fila), 0.5, LINEA))
    for fila in detalles:
        estilo += [
            ("TEXTCOLOR", (0, fila), (-1, fila), TINTA_SUAVE),
            ("LEFTPADDING", (0, fila), (0, fila), 16),
            ("TOPPADDING", (0, fila), (-1, fila), 1),
        ]
    if total is not None:
        estilo += [
            ("FONTNAME", (0, total), (-1, total), "Helvetica-Bold"),
            ("FONTSIZE", (0, total), (-1, total), 10),
            ("LINEABOVE", (0, total), (-1, total), 1, TINTA),
            ("TOPPADDING", (0, total), (-1, total), 6),
        ]
    for columna, fila in ceros:
        estilo += [
            ("TEXTCOLOR", (columna, fila), (columna, fila), TINTA_TENUE),
            ("FONTNAME", (columna, fila), (columna, fila), "Helvetica"),
        ]
    tabla_pdf = Table(datos, colWidths=_anchos(tabla.columnas), repeatRows=1, hAlign="LEFT")
    tabla_pdf.setStyle(TableStyle(estilo))
    contenido.append(tabla_pdf)
    if tabla.nota:
        contenido += [Spacer(1, 4 * mm), Paragraph(tabla.nota, estilos["Italic"])]
    documento.build(contenido)
    return salida.getvalue()
