"""Ajustes visuales después de H7 (DEC-201): un solo título por pantalla y botón ocupado."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db


def _usuario(rol):
    return Usuario.objects.create_user(
        username=f"u-{rol.lower()}",
        password="clave-de-prueba-123",
        nombre_completo="Usuario de prueba",
        rol=rol,
    )


@pytest.mark.parametrize(
    ("rol", "ruta", "titulo"),
    [
        (Rol.ADMINISTRADOR, "inicio", "Hola, Usuario de prueba"),
        (Rol.ADMINISTRADOR, "catalogo:productos", "Productos"),
        (Rol.ADMINISTRADOR, "clientes:clientes", "Clientes"),
        (Rol.CAJERA, "inicio", "Hola, Usuario de prueba"),
        (Rol.CAJERA, "ventas:nueva", "Nueva venta"),
        (Rol.DUENIO, "reportes:inicio", "Reportes"),
    ],
)
def test_dec201_cada_pantalla_tiene_un_solo_h1_y_es_su_titulo(client, rol, ruta, titulo):
    client.force_login(_usuario(rol))

    contenido = client.get(reverse(ruta), follow=True).content.decode()

    h1 = re.findall(r"<h1\b[^>]*>(.*?)</h1>", contenido, re.S)
    assert len(h1) == 1
    assert re.sub(r"<[^>]+>|\s+", " ", h1[0]).strip() == titulo


@pytest.mark.parametrize(
    ("archivo", "textos"),
    [
        ("venta.js", ["Registrando venta…", "Dando de alta…"]),
        ("ingreso.js", ["Registrando ingreso…", "Dando de alta…"]),
    ],
)
def test_dec201_los_botones_que_esperan_al_servidor_avisan_que_estan_ocupados(archivo, textos):
    codigo = (Path(settings.BASE_DIR) / "static" / "js" / archivo).read_text()

    assert 'setAttribute("aria-busy", "true")' in codigo
    for texto in textos:
        assert re.search(rf'ocupado\(\w+, "{texto}"\);', codigo)
    # Cada botón vuelve a su estado al terminar, haya error o no.
    assert codigo.count("ocupado(guardar);") == 1
    assert codigo.count("ocupado(confirmar);") == 1
