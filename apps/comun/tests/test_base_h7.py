"""H7, etapa 1: opción actual del menú (S-5, DEC-191), marca o logo (S-4, DEC-190) y
recursos propios sin CDN (S-3, DEC-189)."""

import re

import pytest
from django.urls import reverse

from apps.comun.menu import FUNCIONES
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db


def _usuario(rol, **extra):
    return Usuario.objects.create_user(
        username=f"u-{rol.lower()}",
        password="clave-de-prueba-123",
        nombre_completo="Usuario de prueba",
        rol=rol,
        **extra,
    )


def _actuales(contenido):
    """Textos de los enlaces del menú marcados con aria-current."""
    menu = contenido.split('<nav aria-label="Menú"', 1)[1].split("</nav>", 1)[0]
    enlaces = re.findall(r"<a [^>]*aria-current=\"page\"[^>]*>(.*?)</a>", menu, re.S)
    return [re.sub(r"<[^>]+>", "", e).strip() for e in enlaces]


@pytest.mark.parametrize(
    ("rol", "ruta", "esperado"),
    [
        (Rol.ADMINISTRADOR, "inicio", ["Inicio"]),
        (Rol.ADMINISTRADOR, "catalogo:productos", ["Productos"]),
        (Rol.ADMINISTRADOR, "catalogo:categorias", ["Productos"]),
        (Rol.ADMINISTRADOR, "caja:medios", ["Medios de pago"]),
        (Rol.ADMINISTRADOR, "clientes:cobrar", ["Clientes"]),
        (Rol.CAJERA, "ventas:nueva", ["Ventas"]),
        (Rol.CAJERA, "ventas:lista", ["Ventas de la caja"]),
        (Rol.CAJERA, "caja:caja", ["Caja"]),
        (Rol.CAJERA, "clientes:cobrar", ["Cobrar cuenta corriente"]),
        (Rol.DUENIO, "reportes:inicio", ["Reportes"]),
    ],
)
def test_s5_el_menu_marca_una_sola_opcion_actual(client, rol, ruta, esperado):
    client.force_login(_usuario(rol))

    contenido = client.get(reverse(ruta), follow=True).content.decode()

    assert _actuales(contenido) == esperado


def test_s5_una_pantalla_interna_marca_su_funcion(client):
    client.force_login(_usuario(Rol.ADMINISTRADOR))

    contenido = client.get(reverse("catalogo:productos") + "nuevo/").content.decode()

    assert _actuales(contenido) == ["Productos"]


def test_s4_sin_archivo_de_logo_se_ve_la_marca_tipografica(client, settings, tmp_path):
    settings.STATICFILES_DIRS = [tmp_path]

    contenido = client.get(reverse("usuarios:ingresar")).content.decode()

    assert "Rojano</span>" in contenido
    assert "img/logo/" not in contenido


def test_s4_con_el_archivo_en_static_img_logo_se_usa_el_logo(client, settings, tmp_path):
    (tmp_path / "img" / "logo").mkdir(parents=True)
    (tmp_path / "img" / "logo" / "logo-rojano.png").write_bytes(b"png")
    (tmp_path / "img" / "logo" / "LEEME.txt").write_text("no es una imagen")
    settings.STATICFILES_DIRS = [tmp_path]

    ingreso = client.get(reverse("usuarios:ingresar")).content.decode()
    client.force_login(_usuario(Rol.CAJERA))
    inicio = client.get(reverse("inicio")).content.decode()

    for contenido in (ingreso, inicio):
        assert 'src="/static/img/logo/logo-rojano.png" alt="Carnicería Rojano"' in contenido


@pytest.mark.parametrize("nombre", ["usuarios:ingresar", "inicio"])
def test_s3_sin_cdn_y_con_favicon(client, nombre):
    if nombre == "inicio":
        client.force_login(_usuario(Rol.ADMINISTRADOR))

    contenido = client.get(reverse(nombre)).content.decode()

    assert "fonts.googleapis.com" not in contenido
    assert "fonts.gstatic.com" not in contenido
    assert 'rel="icon" href="/static/img/favicon.svg"' in contenido


def test_cada_funcion_del_menu_tiene_su_propio_icono():
    iconos = [f.icono for f in FUNCIONES]

    assert all(iconos)
    assert len(set(iconos)) == len(iconos)


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.CAJERA, Rol.DUENIO])
def test_inicio_va_dentro_del_grupo_menu(client, rol):
    client.force_login(_usuario(rol))

    contenido = client.get(reverse("inicio")).content.decode()
    menu = contenido.split('<nav aria-label="Menú"', 1)[1]

    inicio = re.search(r">\s*Inicio\s*</a>", menu)

    assert inicio and menu.index(">Menú</p>") < inicio.start()


def test_los_dias_de_la_semana_llevan_tilde():
    import datetime

    from apps.comun.templatetags.fechas import con_dia

    assert con_dia(datetime.date(2026, 11, 4)) == "Mié 4/11/2026"
    assert con_dia(datetime.date(2026, 11, 7), "j/m") == "Sáb 7/11"
