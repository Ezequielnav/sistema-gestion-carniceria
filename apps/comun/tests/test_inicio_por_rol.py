"""CP-126 y CP-127: los dueños solo en Reportes e inicio por rol (H5, etapa 1)."""

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.caja.models import EstadoCaja
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

# Lo que un dueño sí abre: el inicio, entrar y salir, los reportes y el reporte de cierre, que
# es parte de la consulta de cierres de CU-09 (DEC-59, DEC-134, DEC-144). El panel tiene su propio
# control (DEC-32) y se prueba en test_admin.py.
PERMITIDAS_AL_DUENIO = {
    "inicio",
    "usuarios:ingresar",
    "usuarios:salir",
    "caja:cierre",
    # CU-09 (H5, etapa 3): todas las pantallas de reportes.
    "reportes:inicio",
    "reportes:ventas",
    "reportes:productos",
    "reportes:ingresos",
    "reportes:medios",
    "reportes:cierres",
}


def _usuario(rol):
    return Usuario.objects.create_user(
        username=f"u-{rol.lower()}",
        password="clave-de-prueba-123",
        nombre_completo="Usuario de prueba",
        rol=rol,
    )


def _pantallas(patrones=None, prefijo="", espacio=""):
    """(nombre, ruta) de cada pantalla de la aplicación, con 1 en los parámetros enteros."""
    for patron in patrones if patrones is not None else get_resolver().url_patterns:
        if isinstance(patron, URLResolver):
            if patron.app_name == "admin":
                continue
            yield from _pantallas(
                patron.url_patterns,
                prefijo + str(patron.pattern),
                patron.namespace or espacio,
            )
        elif isinstance(patron, URLPattern) and patron.name:
            ruta = "/" + (prefijo + str(patron.pattern)).replace("<int:pk>", "1")
            yield (f"{espacio}:{patron.name}" if espacio else patron.name), ruta


PANTALLAS = sorted(_pantallas())


# CP-126 (DEC-134, RN-06)


def test_cp126_la_lista_de_pantallas_cubre_todos_los_modulos():
    nombres = {nombre for nombre, _ in PANTALLAS}

    assert {"ventas:nueva", "clientes:cobrar", "catalogo:productos", "caja:caja"} <= nombres
    assert all(r.startswith("/") and "<" not in r for _, r in PANTALLAS)


@pytest.mark.parametrize(
    ("nombre", "ruta"), [p for p in PANTALLAS if p[0] not in PERMITIDAS_AL_DUENIO]
)
def test_cp126_el_duenio_recibe_403_en_toda_pantalla_que_no_es_de_reportes(client, nombre, ruta):
    client.force_login(_usuario(Rol.DUENIO))

    # 405 es una pantalla que no acepta ese método: tampoco muestra nada.
    assert client.get(ruta).status_code in (403, 405), nombre
    assert client.post(ruta).status_code in (403, 405), nombre


def test_cp126_el_inicio_del_duenio_solo_tiene_reportes_sin_totales(client, venta):
    client.force_login(_usuario(Rol.DUENIO))

    respuesta = client.get(reverse("inicio"))
    contenido = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert [t.name for t in respuesta.templates][0] == "comun/inicio_duenio.html"
    assert [f.nombre for f in respuesta.context["menu"]] == ["Reportes"]
    assert "total_ventas" not in respuesta.context
    assert "Ventas de hoy" not in contenido
    assert "Últimas ventas" not in contenido


# CP-127 (DEC-137, DEC-148) y R-4 (DEC-154)


def _sin_totales(monkeypatch):
    """Si el inicio de la cajera calcula un total del negocio, la prueba falla (R-4)."""

    def no_llamar(*args, **kwargs):
        raise AssertionError("el inicio de la cajera no calcula totales")

    for nombre in (
        "resumen_del_dia",
        "ultimas_ventas",
        "cantidad_de_productos_activos",
        "cantidad_con_stock_bajo",
    ):
        monkeypatch.setattr(f"apps.comun.views.{nombre}", no_llamar)


def test_cp127_con_caja_abierta_la_cajera_ve_su_caja_y_sus_tres_operaciones(
    client, caja, monkeypatch
):
    _sin_totales(monkeypatch)
    client.force_login(caja.usuario)

    respuesta = client.get(reverse("inicio"))
    contenido = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert respuesta.context["caja"] == caja
    assert "Abierta" in contenido
    assert "Turno mañana" in contenido
    assert caja.usuario.nombre_completo in contenido
    for url in ("ventas:nueva", "clientes:cobrar", "caja:cerrar"):
        assert f'href="{reverse(url)}"' in contenido
    assert "Abrir caja" not in contenido


def test_cp127_sin_caja_abierta_avisa_y_lleva_a_abrirla(client, caja, monkeypatch):
    caja.estado = EstadoCaja.CERRADA
    caja.save()
    _sin_totales(monkeypatch)
    client.force_login(caja.usuario)

    respuesta = client.get(reverse("inicio"))
    contenido = respuesta.content.decode()

    assert respuesta.context["caja"] is None
    assert "No hay caja abierta." in contenido
    assert f'href="{reverse("caja:caja")}"' in contenido
    # Los tres accesos siguen: cada pantalla avisa si falta la caja (DEC-148).
    for url in ("ventas:nueva", "clientes:cobrar", "caja:cerrar"):
        assert f'href="{reverse(url)}"' in contenido


def test_cp127_el_inicio_de_la_cajera_no_muestra_totales_del_negocio(client, venta):
    client.force_login(venta.caja.usuario)

    respuesta = client.get(reverse("inicio"))
    contenido = respuesta.content.decode()

    for clave in ("total_ventas", "ultimas_ventas", "productos_activos", "stock_bajo"):
        assert clave not in respuesta.context
    for texto in ("Ventas de hoy", "Últimas ventas", "Productos activos", "Stock bajo"):
        assert texto not in contenido
