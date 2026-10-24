from django.urls import path

from apps.usuarios.views import IngresarView, SalirView

app_name = "usuarios"

urlpatterns = [
    path("ingresar/", IngresarView.as_view(), name="ingresar"),
    path("salir/", SalirView.as_view(), name="salir"),
]
