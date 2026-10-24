from django.contrib.auth.forms import AuthenticationForm

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
