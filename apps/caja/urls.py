from django.urls import path

from apps.caja import views

app_name = "caja"

urlpatterns = [
    path("", views.caja, name="caja"),
    path("egreso/", views.egreso, name="egreso"),
    path("cerrar/", views.cerrar, name="cerrar"),
    path("<int:pk>/cierre/", views.cierre, name="cierre"),
    # DEC-155 (L18): medios de pago, solo el Administrador.
    path("medios/", views.medios, name="medios"),
    path("medios/nuevo/", views.medio_nuevo, name="medio_nuevo"),
    path("medios/<int:pk>/editar/", views.medio_editar, name="medio_editar"),
    path("medios/<int:pk>/activo/", views.medio_activo, name="medio_activo"),
]
