import pytest
from django.db import IntegrityError, transaction

from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db


def test_cp51_la_contrasena_se_guarda_con_hash():
    usuario = Usuario.objects.create_user(
        username="admin1",
        password="clave-de-prueba-123",
        nombre_completo="Admin",
        rol=Rol.ADMINISTRADOR,
    )

    usuario.refresh_from_db()
    assert usuario.password != "clave-de-prueba-123"
    assert "clave-de-prueba-123" not in usuario.password
    assert usuario.password.startswith(("pbkdf2_sha256$", "argon2$", "bcrypt"))
    assert usuario.check_password("clave-de-prueba-123")


def test_cp59_nombre_de_usuario_repetido_se_rechaza(usuario):
    with pytest.raises(IntegrityError), transaction.atomic():
        Usuario.objects.create_user(
            username=usuario.username,
            password="otra-clave-456",
            nombre_completo="Otra",
            rol=Rol.CAJERA,
        )


@pytest.mark.parametrize("rol", ["CAJERO", ""])
def test_rol_fuera_de_la_lista_se_rechaza(rol):
    with pytest.raises(IntegrityError), transaction.atomic():
        Usuario.objects.create_user(
            username="x", password="clave-456", nombre_completo="X", rol=rol
        )


def test_el_nombre_completo_es_el_nombre_que_muestra_el_sistema(usuario):
    assert usuario.get_full_name() == "Cajera Uno"
    assert usuario.get_short_name() == "Cajera"
