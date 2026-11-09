from django.urls import path

from apps.clientes import views

app_name = "clientes"

urlpatterns = [
    path("", views.clientes, name="clientes"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/baja/", views.baja, name="baja"),
    path("<int:pk>/reactivar/", views.reactivar_cliente, name="reactivar"),
    path("<int:pk>/", views.estado, name="estado"),
    path("<int:pk>/condiciones/", views.condiciones, name="condiciones"),
    path("<int:pk>/saldo-inicial/", views.saldo_inicial, name="saldo_inicial"),
    path("<int:pk>/saldo-inicial/anular/", views.saldo_inicial_anular, name="saldo_inicial_anular"),
    path("buscar/", views.buscar, name="buscar"),
    path("cobrar/", views.cobrar, name="cobrar"),
    path("cobros/<int:pk>/", views.cobro, name="cobro"),
    path("cobros/<int:pk>/anular/", views.cobro_anular, name="cobro_anular"),
    path("cobros/<int:pk>/comprobante/", views.comprobante, name="comprobante"),
]
