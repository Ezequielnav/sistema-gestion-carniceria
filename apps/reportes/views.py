from collections.abc import Callable
from dataclasses import dataclass

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from apps.comun.permisos import requiere_funcion
from apps.reportes import exportar, services
from apps.reportes.forms import RangoForm
from apps.reportes.resumen import resumen as calcular_resumen
from apps.usuarios.models import Rol

POR_PAGINA = 25

# RF-43, DEC-146: los cuatro reportes de RF-42 se exportan; la consulta de cierres no
# (DEC-144: el reporte de cierre de cada caja se imprime desde el navegador).
FORMATOS = {
    "excel": (
        exportar.excel,
        "xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "pdf": (exportar.pdf, "pdf", "application/pdf"),
}


def _paginar_ranking(request, reporte):
    """Producto más vendido pagina de a 25 en pantalla (DEC-141); se exporta completo."""
    pagina = Paginator(reporte["productos"], POR_PAGINA).get_page(request.GET.get("pagina"))
    return {**reporte, "pagina": pagina}, {}


def _listar_cajas(request, reporte):
    return {"cajas": list(reporte)}, {}


def _preparar_resumen(request, reporte):
    """Gráficos del Resumen y, solo para el Administrador, los enlaces a clientes, productos y
    proveedores (DEC-134, DEC-158)."""
    return reporte, {
        "graficos": _graficos(reporte),
        "es_admin": request.user.rol == Rol.ADMINISTRADOR,
    }


@dataclass(frozen=True)
class Reporte:
    """Una pestaña de Reportes: su servicio, el rango por defecto en días hasta hoy (DEC-145) y,
    si hace falta, cómo prepara la pantalla: (request, reporte) -> (reporte, contexto extra)."""

    nombre: str
    titulo: str
    calcular: Callable
    dias_por_defecto: int = 1
    preparar: Callable | None = None


# El Resumen (DEC-158), los reportes en el orden de RF-42 y la consulta de cierres (DEC-144).
REPORTES = [
    Reporte(
        "resumen", "Resumen", calcular_resumen, dias_por_defecto=30, preparar=_preparar_resumen
    ),
    Reporte("ventas", "Ventas diarias", services.ventas_diarias),
    Reporte(
        "productos",
        "Producto más vendido",
        services.productos_mas_vendidos,
        preparar=_paginar_ranking,
    ),
    Reporte("ingresos", "Ingresos por día", services.ingresos_por_dia),
    Reporte("medios", "Totales por medio de pago", services.totales_por_medio),
    Reporte("cierres", "Cierres de caja", services.cierres, preparar=_listar_cajas),
]
PESTANAS = [(r.nombre, r.titulo) for r in REPORTES]


@requiere_funcion("Reportes")
@require_GET
def inicio(request):
    """Abre el Resumen (DEC-158) con el rango que traiga la dirección."""
    destino = reverse("reportes:resumen")
    return redirect(f"{destino}?{request.GET.urlencode()}" if request.GET else destino)


def _pantalla(definicion):
    nombre = definicion.nombre

    @requiere_funcion("Reportes")
    @require_GET
    def vista(request):
        """CU-09 a pedido y en solo lectura (DEC-136, RF-45)."""
        form = RangoForm(request.GET, dias=definicion.dias_por_defecto)
        contexto = {
            "form": form,
            "titulo": definicion.titulo,
            "activa": nombre,
            "pestanas": PESTANAS,
            "rango": "",
        }
        if form.is_valid():
            desde, hasta = form.cleaned_data["desde"], form.cleaned_data["hasta"]
            contexto["rango"] = f"desde={desde.isoformat()}&hasta={hasta.isoformat()}"
            reporte = definicion.calcular(request.user, desde, hasta)
            # Los cuatro reportes de RF-42 se exportan; el Resumen y los cierres, no.
            contexto["exporta"] = nombre in exportar.TABLAS
            formato = request.GET.get("formato")
            if formato in FORMATOS and contexto["exporta"]:
                archivo = _exportar(nombre, formato, reporte, desde, hasta)
                if archivo:
                    return archivo
                # RF-44: sin datos no hay archivo; la pantalla muestra el aviso.
                messages.info(request, "Sin registros disponibles: no hay nada para exportar.")
            if definicion.preparar:
                reporte, extra = definicion.preparar(request, reporte)
                contexto.update(extra)
            contexto["reporte"] = reporte
        return render(request, f"reportes/{nombre}.html", contexto)

    vista.__name__ = nombre
    return vista


def _graficos(datos):
    """Series del Resumen; los montos van como texto y se convierten solo para dibujar."""
    serie = datos["serie"]
    # Con un rango que cruza de año, la fecha lleva el año para no confundir días.
    formato = "j/m/y" if serie and serie[0][0].year != serie[-1][0].year else "j/m"
    return {
        "serie": {
            "etiquetas": [date_format(fecha, formato) for fecha, _ in serie],
            "valores": [str(total) for _, total in serie],
        },
        "medios": {
            "etiquetas": [m["medio"] for m in datos["medios"]],
            "valores": [str(m["ventas"]) for m in datos["medios"]],
        },
        "top": {
            "etiquetas": [p["producto__nombre"] for p in datos["top"]],
            "valores": [str(p["importe"]) for p in datos["top"]],
        },
    }


def _exportar(nombre, formato, reporte, desde, hasta):
    """El archivo con el mismo resultado que la pantalla (R-3), o None si no hay datos."""
    tablas = exportar.TABLAS_PDF if formato == "pdf" else exportar.TABLAS
    tabla = tablas[nombre](reporte)
    if not tabla.filas:
        return None
    generar, extension, tipo = FORMATOS[formato]
    respuesta = HttpResponse(generar(tabla, desde, hasta), content_type=tipo)
    archivo = exportar.nombre_de_archivo(slugify(tabla.titulo), desde, hasta, extension)
    respuesta["Content-Disposition"] = f'attachment; filename="{archivo}"'
    return respuesta


VISTAS = {r.nombre: _pantalla(r) for r in REPORTES}
resumen = VISTAS["resumen"]
ventas = VISTAS["ventas"]
productos = VISTAS["productos"]
ingresos = VISTAS["ingresos"]
medios = VISTAS["medios"]
cierres = VISTAS["cierres"]
