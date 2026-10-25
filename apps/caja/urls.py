from django.urls import path

from apps.caja import views

app_name = "caja"

urlpatterns = [
    path("", views.caja, name="caja"),
]
