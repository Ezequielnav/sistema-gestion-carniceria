from django.contrib import admin
from django.urls import include, path

from apps.comun.views import inicio

# Título del índice del panel, igual que el ítem "Panel" de su menú (DEC-30).
admin.site.index_title = "Panel"

urlpatterns = [
    path("", inicio, name="inicio"),
    path("", include("apps.usuarios.urls")),
    path("caja/", include("apps.caja.urls")),
    path("ventas/", include("apps.ventas.urls")),
    path("productos/", include("apps.catalogo.urls")),
    path("admin/", admin.site.urls),
]
