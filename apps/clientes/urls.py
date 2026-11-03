from django.urls import path

from apps.clientes import views

app_name = "clientes"

urlpatterns = [
    path("", views.clientes, name="clientes"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/baja/", views.baja, name="baja"),
    path("<int:pk>/reactivar/", views.reactivar_cliente, name="reactivar"),
    path("buscar/", views.buscar, name="buscar"),
]
