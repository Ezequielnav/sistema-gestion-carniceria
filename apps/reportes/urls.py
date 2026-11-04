from django.urls import path

from apps.reportes import views

app_name = "reportes"

# CU-09 (DEC-136, DEC-140 a DEC-144): una pantalla por reporte, con el rango en la dirección.
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("ventas-diarias/", views.ventas, name="ventas"),
    path("productos/", views.productos, name="productos"),
    path("ingresos/", views.ingresos, name="ingresos"),
    path("medios-de-pago/", views.medios, name="medios"),
    path("cierres/", views.cierres, name="cierres"),
]
