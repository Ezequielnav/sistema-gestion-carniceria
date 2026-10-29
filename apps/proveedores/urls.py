from django.urls import path

from apps.proveedores import views

app_name = "proveedores"

urlpatterns = [
    path("", views.proveedores, name="proveedores"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/baja/", views.baja, name="baja"),
    path("<int:pk>/reactivar/", views.reactivar_proveedor, name="reactivar"),
    path("ingresos/", views.ingresos, name="ingresos"),
    path("ingresos/nuevo/", views.ingreso_nuevo, name="ingreso_nuevo"),
    path("ingresos/buscar/", views.ingreso_buscar, name="ingreso_buscar"),
    path("ingresos/producto/", views.ingreso_producto, name="ingreso_producto"),
    path("ingresos/confirmar/", views.ingreso_confirmar, name="ingreso_confirmar"),
    path("ingresos/<int:pk>/", views.ingreso, name="ingreso"),
    path("ingresos/<int:pk>/anular/", views.ingreso_anular, name="ingreso_anular"),
]
