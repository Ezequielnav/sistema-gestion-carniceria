import pytest

from apps.reportes.tests.datos import armar_escenario, usuario
from apps.usuarios.models import Rol


@pytest.fixture
def admin(db):
    return usuario("admin", Rol.ADMINISTRADOR)


@pytest.fixture
def escenario(admin):
    return armar_escenario(admin)
