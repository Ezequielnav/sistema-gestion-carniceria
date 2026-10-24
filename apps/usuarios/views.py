from django.contrib.auth.views import LoginView, LogoutView

from apps.usuarios.forms import IngresoForm


class IngresarView(LoginView):
    """CU-10: inicio de sesión con sesiones de Django (D-06)."""

    template_name = "usuarios/ingresar.html"
    authentication_form = IngresoForm
    redirect_authenticated_user = True


class SalirView(LogoutView):
    """CU-10, A3: cierra la sesión (solo por POST) y vuelve al ingreso."""
