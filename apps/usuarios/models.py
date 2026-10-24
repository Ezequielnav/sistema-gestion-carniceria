from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

from apps.comun.models import ModeloBase


class Rol(models.TextChoices):
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    CAJERA = "CAJERA", "Cajera"
    DUENIO = "DUENIO", "Dueño"


class Usuario(AbstractUser, ModeloBase):
    """Entidad usuario de 05 (4.1) sobre el modelo de usuario de Django (DEC-27).

    nombre_usuario -> username, contrasena_hash -> password, activo -> is_active.
    """

    # nombre_completo reemplaza a first_name y last_name.
    first_name = None
    last_name = None
    nombre_completo = models.CharField(max_length=150)
    telefono = models.CharField(max_length=30, blank=True)
    rol = models.CharField(max_length=13, choices=Rol.choices)
    puede_crear_productos = models.BooleanField(default=False)

    REQUIRED_FIELDS = ["nombre_completo", "rol"]

    class Meta:
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.CheckConstraint(condition=Q(rol__in=Rol.values), name="usuario_rol_valido"),
            # DEC-32: solo el Administrador accede al panel de Django.
            models.CheckConstraint(
                condition=Q(rol=Rol.ADMINISTRADOR) | Q(is_staff=False, is_superuser=False),
                name="usuario_panel_solo_administrador",
                violation_error_message=(
                    "Solo un usuario con rol Administrador puede acceder al panel "
                    "o ser superusuario."
                ),
            ),
        ]

    def __str__(self):
        return self.username

    # Sin first_name ni last_name: el nombre que muestra el panel sale de nombre_completo.
    def get_full_name(self):
        return self.nombre_completo

    def get_short_name(self):
        return self.nombre_completo.split(" ")[0] if self.nombre_completo else self.username
