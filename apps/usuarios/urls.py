from django.urls import path

from apps.usuarios import views

app_name = "usuarios"

urlpatterns = [
    path("ingresar/", views.IngresarView.as_view(), name="ingresar"),
    path("salir/", views.SalirView.as_view(), name="salir"),
    # CU-14 (DEC-149)
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/nuevo/", views.nuevo, name="nuevo"),
    path("usuarios/<int:pk>/editar/", views.editar, name="editar"),
    path("usuarios/<int:pk>/baja/", views.baja, name="baja"),
    path("usuarios/<int:pk>/reactivar/", views.reactivar_usuario, name="reactivar"),
    path("usuarios/<int:pk>/contrasena/", views.contrasena, name="contrasena"),
]
