"""runserver que, en desarrollo, sirve los estáticos sin caché.

El servidor de desarrollo manda los estáticos solo con Last-Modified y el navegador puede
seguir usando un JS viejo después de un cambio. Con DEBUG se agrega Cache-Control: no-cache:
el navegador vuelve a preguntar cada vez y, si el archivo no cambió, recibe un 304.
Producción no usa runserver; ahí van los estáticos con hash en el nombre (L3 de 07).
"""

from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.staticfiles.management.commands.runserver import Command as RunserverCommand


class EstaticosSinCache(StaticFilesHandler):
    def serve(self, request):
        respuesta = super().serve(request)
        respuesta["Cache-Control"] = "no-cache"
        return respuesta


class Command(RunserverCommand):
    def get_handler(self, *args, **options):
        handler = super().get_handler(*args, **options)
        if settings.DEBUG and isinstance(handler, StaticFilesHandler):
            return EstaticosSinCache(handler.application)
        return handler
