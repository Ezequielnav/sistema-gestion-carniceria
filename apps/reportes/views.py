from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from apps.comun.permisos import requiere_funcion
from apps.reportes import exportar, services
from apps.reportes.forms import RangoForm

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

# (nombre de la URL, título de la pestaña, función del servicio) en el orden de RF-42, más la
# consulta de cierres (DEC-144).
REPORTES = [
    ("ventas", "Ventas diarias", services.ventas_diarias),
    ("productos", "Producto más vendido", services.productos_mas_vendidos),
    ("ingresos", "Ingresos por día", services.ingresos_por_dia),
    ("medios", "Totales por medio de pago", services.totales_por_medio),
    ("cierres", "Cierres de caja", services.cierres),
]


@requiere_funcion("Reportes")
@require_GET
def inicio(request):
    """Abre el primer reporte con el rango que traiga la dirección."""
    destino = reverse("reportes:ventas")
    return redirect(f"{destino}?{request.GET.urlencode()}" if request.GET else destino)


def _pantalla(nombre):
    titulo, calcular = next((t, f) for n, t, f in REPORTES if n == nombre)

    @requiere_funcion("Reportes")
    @require_GET
    def vista(request):
        """CU-09 a pedido y en solo lectura (DEC-136, RF-45)."""
        form = RangoForm(request.GET)
        contexto = {
            "form": form,
            "titulo": titulo,
            "activa": nombre,
            "pestanas": [(n, t) for n, t, _ in REPORTES],
            "rango": "",
        }
        if form.is_valid():
            desde, hasta = form.cleaned_data["desde"], form.cleaned_data["hasta"]
            contexto["rango"] = f"desde={desde.isoformat()}&hasta={hasta.isoformat()}"
            reporte = calcular(request.user, desde, hasta)
            formato = request.GET.get("formato")
            if formato in FORMATOS and nombre in exportar.TABLAS:
                archivo = _exportar(nombre, formato, reporte, desde, hasta)
                if archivo:
                    return archivo
                # RF-44: sin datos no hay archivo; la pantalla muestra el aviso.
                messages.info(request, "Sin registros disponibles: no hay nada para exportar.")
            if nombre == "productos":
                pagina = Paginator(reporte["productos"], POR_PAGINA).get_page(
                    request.GET.get("pagina")
                )
                reporte = {**reporte, "pagina": pagina}
            elif nombre == "cierres":
                reporte = {"cajas": list(reporte)}
            contexto["reporte"] = reporte
            contexto["exporta"] = nombre in exportar.TABLAS
        return render(request, f"reportes/{nombre}.html", contexto)

    vista.__name__ = nombre
    return vista


def _exportar(nombre, formato, reporte, desde, hasta):
    """El archivo con el mismo resultado que la pantalla (R-3), o None si no hay datos."""
    tabla = exportar.TABLAS[nombre](reporte)
    if not tabla.filas:
        return None
    generar, extension, tipo = FORMATOS[formato]
    respuesta = HttpResponse(generar(tabla, desde, hasta), content_type=tipo)
    archivo = exportar.nombre_de_archivo(slugify(tabla.titulo), desde, hasta, extension)
    respuesta["Content-Disposition"] = f'attachment; filename="{archivo}"'
    return respuesta


ventas = _pantalla("ventas")
productos = _pantalla("productos")
ingresos = _pantalla("ingresos")
medios = _pantalla("medios")
cierres = _pantalla("cierres")
