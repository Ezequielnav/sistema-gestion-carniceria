from django.urls import path

from apps.caja import views

app_name = "caja"

urlpatterns = [
    path("", views.caja, name="caja"),
    path("egreso/", views.egreso, name="egreso"),
    path("cerrar/", views.cerrar, name="cerrar"),
    path("<int:pk>/cierre/", views.cierre, name="cierre"),
]
