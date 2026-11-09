import copy

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.forms.models import fields_for_model

from apps.usuarios.models import Rol, Usuario
from apps.usuarios.services import CAMPOS_EDITABLES

# Mismo mensaje para credenciales inválidas y usuario dado de baja: no revela si la cuenta
# existe (CU-10, A1 y A2).
MENSAJE_GENERICO = "Usuario o contraseña incorrectos."


class IngresoForm(AuthenticationForm):
    error_messages = {
        "invalid_login": MENSAJE_GENERICO,
        "inactive": MENSAJE_GENERICO,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuario"
        self.fields["password"].label = "Contraseña"
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"


# CU-14 (DEC-149): las reglas (permisos, rol, último Administrador) las aplica el servicio.

ETIQUETAS = {
    "username": "Usuario",
    "nombre_completo": "Nombre completo",
    "telefono": "Teléfono",
    "email": "Email",
    "rol": "Rol",
    "puede_crear_productos": "Puede crear productos",
}
AYUDAS = {
    "username": "Con el que ingresa. Letras, números y @ . + - _",
    "telefono": "Opcional.",
    "email": "Opcional.",
    "puede_crear_productos": "Solo para la cajera.",  # RN-05
}


def _validar_repetida(form, datos):
    if datos.get("password1") and datos.get("password1") != datos.get("password2"):
        form.add_error("password2", "Las contraseñas no coinciden.")
    return datos


def _estilos(form):
    for campo in form.fields.values():
        clase = "casilla" if isinstance(campo.widget, forms.CheckboxInput) else "campo"
        campo.widget.attrs["class"] = clase


class ContrasenaForm(forms.Form):
    """Contraseña nueva repetida; los validadores de Django los aplica el servicio."""

    password1 = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Al menos 8 caracteres, que no sean solo números ni una contraseña común.",
    )
    password2 = forms.CharField(
        label="Repetir contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilos(self)

    def clean(self):
        return _validar_repetida(self, super().clean())


class UsuarioForm(forms.Form):
    """Datos y rol de un usuario (DEC-149). En el alta suma la contraseña inicial."""

    def __init__(self, *args, es_alta=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(
            fields_for_model(Usuario, fields=CAMPOS_EDITABLES, labels=ETIQUETAS, help_texts=AYUDAS)
        )
        self.fields["rol"].choices = [("", "Elegí un rol"), *Rol.choices]
        if es_alta:
            self.fields.update(copy.deepcopy(ContrasenaForm.base_fields))
        _estilos(self)

    def clean(self):
        return _validar_repetida(self, super().clean())
