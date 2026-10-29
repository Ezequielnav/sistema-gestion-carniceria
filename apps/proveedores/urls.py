from django.urls import path

from apps.proveedores import views

app_name = "proveedores"

urlpatterns = [
    path("", views.proveedores, name="proveedores"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/baja/", views.baja, name="baja"),
    path("<int:pk>/reactivar/", views.reactivar_proveedor, name="reactivar"),
]
