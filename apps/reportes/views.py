from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.comun.permisos import requiere_funcion
from apps.reportes import services
from apps.reportes.forms import RangoForm

POR_PAGINA = 25

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
            if nombre == "productos":
                pagina = Paginator(reporte["productos"], POR_PAGINA).get_page(
                    request.GET.get("pagina")
                )
                reporte = {**reporte, "pagina": pagina}
            elif nombre == "cierres":
                reporte = {"cajas": list(reporte)}
            contexto["reporte"] = reporte
        return render(request, f"reportes/{nombre}.html", contexto)

    vista.__name__ = nombre
    return vista


ventas = _pantalla("ventas")
productos = _pantalla("productos")
ingresos = _pantalla("ingresos")
medios = _pantalla("medios")
cierres = _pantalla("cierres")
