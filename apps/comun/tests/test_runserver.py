"""En desarrollo, runserver sirve los estáticos sin caché para no quedar con JS viejo."""

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.management import get_commands
from django.test import RequestFactory, override_settings

from apps.comun.management.commands.runserver import Command, EstaticosSinCache


def _handler():
    return Command().get_handler(use_static_handler=True, insecure_serving=False)


def test_el_runserver_del_proyecto_reemplaza_al_de_staticfiles():
    assert get_commands()["runserver"] == "apps.comun"


@override_settings(DEBUG=True)
def test_con_debug_los_estaticos_se_sirven_sin_cache():
    handler = _handler()
    assert isinstance(handler, EstaticosSinCache)

    respuesta = handler.get_response(RequestFactory().get("/static/js/venta.js"))

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-cache"
    assert "Last-Modified" in respuesta


@override_settings(DEBUG=False)
def test_sin_debug_no_cambia_nada():
    assert not isinstance(_handler(), StaticFilesHandler)
