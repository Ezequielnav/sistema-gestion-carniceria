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
from apps.reportes.tablero import tablero
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

# (nombre de la URL, título de la pestaña, función del servicio): el Resumen (DEC-158), los
# reportes en el orden de RF-42 y la consulta de cierres (DEC-144).
REPORTES = [
    ("resumen", "Resumen", tablero),
    ("ventas", "Ventas diarias", services.ventas_diarias),
    ("productos", "Producto más vendido", services.productos_mas_vendidos),
    ("ingresos", "Ingresos por día", services.ingresos_por_dia),
    ("medios", "Totales por medio de pago", services.totales_por_medio),
    ("cierres", "Cierres de caja", services.cierres),
]


@requiere_funcion("Reportes")
@require_GET
def inicio(request):
    """Abre el Resumen (DEC-158) con el rango que traiga la dirección."""
    destino = reverse("reportes:resumen")
    return redirect(f"{destino}?{request.GET.urlencode()}" if request.GET else destino)


def _pantalla(nombre):
    titulo, calcular = next((t, f) for n, t, f in REPORTES if n == nombre)

    @requiere_funcion("Reportes")
    @require_GET
    def vista(request):
        """CU-09 a pedido y en solo lectura (DEC-136, RF-45)."""
        # El Resumen abre con los últimos 30 días; cada reporte, con el día de hoy (DEC-145).
        form = RangoForm(request.GET, dias=30 if nombre == "resumen" else 1)
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
            elif nombre == "resumen":
                contexto["graficos"] = _graficos(reporte)
                # Los enlaces a clientes, productos y proveedores, solo para él (DEC-134).
                contexto["es_admin"] = request.user.rol == Rol.ADMINISTRADOR
            contexto["reporte"] = reporte
            contexto["exporta"] = nombre in exportar.TABLAS
        return render(request, f"reportes/{nombre}.html", contexto)

    vista.__name__ = nombre
    return vista


def _graficos(datos):
    """Series del Resumen; los montos van como texto y se convierten solo para dibujar."""
    return {
        "serie": {
            "etiquetas": [date_format(fecha, "j/m") for fecha, _ in datos["serie"]],
            "valores": [str(total) for _, total in datos["serie"]],
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
    tabla = exportar.TABLAS[nombre](reporte)
    if not tabla.filas:
        return None
    generar, extension, tipo = FORMATOS[formato]
    respuesta = HttpResponse(generar(tabla, desde, hasta), content_type=tipo)
    archivo = exportar.nombre_de_archivo(slugify(tabla.titulo), desde, hasta, extension)
    respuesta["Content-Disposition"] = f'attachment; filename="{archivo}"'
    return respuesta


resumen = _pantalla("resumen")
ventas = _pantalla("ventas")
productos = _pantalla("productos")
ingresos = _pantalla("ingresos")
medios = _pantalla("medios")
cierres = _pantalla("cierres")
