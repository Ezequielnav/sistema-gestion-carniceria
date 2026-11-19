"""DEC-202: pantalla de ingreso (texto de ejemplo, recuadro, firma) y ojo en las contraseñas."""

import pytest
from django.urls import reverse

from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db


def test_dec202_el_ingreso_tiene_texto_de_ejemplo_titulo_y_firma(client):
    contenido = client.get(reverse("usuarios:ingresar")).content.decode()

    assert 'placeholder="Tu usuario"' in contenido
    assert 'placeholder="Tu contraseña"' in contenido
    assert ">Te damos la bienvenida</h2>" in contenido
    assert contenido.count('class="icono-campo shrink-0"') == 2
    assert "© 2026 Desarrollador: Ezequiel Navarro Sahad" in contenido
    assert "js/contrasena.js" in contenido
    # Un comentario de plantilla mal cerrado se vería en pantalla.
    assert "{#" not in contenido


def test_dec202_las_pantallas_con_contrasena_cargan_el_ojo(client):
    admin = Usuario.objects.create_user(
        username="admin", password="clave-de-prueba-123", rol=Rol.ADMINISTRADOR
    )
    client.force_login(admin)

    contenido = client.get(reverse("usuarios:nuevo")).content.decode()

    assert 'type="password"' in contenido
    assert "js/contrasena.js" in contenido
