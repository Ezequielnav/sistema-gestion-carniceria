from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from apps.usuarios.models import Usuario

# Grupos con el estilo de Unfold (DEC-30).
admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    # Adapta UserAdmin a los campos de DEC-27 (sin first_name ni last_name).
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Datos personales", {"fields": ("nombre_completo", "telefono", "email")}),
        (
            "Rol y permisos",
            {
                "fields": (
                    "rol",
                    "puede_crear_productos",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "nombre_completo", "rol", "password1", "password2"),
            },
        ),
    )
    list_display = ("username", "nombre_completo", "rol", "puede_crear_productos", "is_active")
    list_filter = ("rol", "is_active")
    search_fields = ("username", "nombre_completo", "email")
    ordering = ("username",)
