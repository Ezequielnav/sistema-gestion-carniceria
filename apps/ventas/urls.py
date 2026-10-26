from django.urls import path

from apps.ventas import views

app_name = "ventas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/anular/", views.anular, name="anular"),
    path("nueva/", views.nueva, name="nueva"),
    path("buscar/", views.buscar, name="buscar"),
    path("producto/", views.producto_nuevo, name="producto_nuevo"),
    path("confirmar/", views.confirmar, name="confirmar"),
    path("<int:pk>/ticket/", views.ticket, name="ticket"),
]
