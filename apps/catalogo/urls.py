from django.urls import path

from apps.catalogo import views

app_name = "catalogo"

urlpatterns = [
    path("", views.productos, name="productos"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/baja/", views.baja, name="baja"),
    path("<int:pk>/reactivar/", views.reactivar_producto, name="reactivar"),
    # DEC-155 (L18): solo el Administrador.
    path("categorias/", views.categorias, name="categorias"),
    path("categorias/nueva/", views.categoria_nueva, name="categoria_nueva"),
    path("categorias/<int:pk>/editar/", views.categoria_editar, name="categoria_editar"),
    path("categorias/<int:pk>/baja/", views.categoria_baja, name="categoria_baja"),
    path("categorias/<int:pk>/reactivar/", views.categoria_reactivar, name="categoria_reactivar"),
    path("ajustes/", views.ajustes, name="ajustes"),
]
