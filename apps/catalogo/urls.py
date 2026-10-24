from django.urls import path

from apps.catalogo import views

app_name = "catalogo"

urlpatterns = [
    path("", views.productos, name="productos"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/baja/", views.baja, name="baja"),
]
