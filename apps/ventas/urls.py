from django.urls import path

from apps.ventas import views

app_name = "ventas"

urlpatterns = [
    path("nueva/", views.nueva, name="nueva"),
    path("buscar/", views.buscar, name="buscar"),
    path("confirmar/", views.confirmar, name="confirmar"),
    path("<int:pk>/ticket/", views.ticket, name="ticket"),
]
