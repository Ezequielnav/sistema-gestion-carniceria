import pytest

from apps.usuarios.models import Rol, Usuario


def _crear(username, rol, **extra):
    return Usuario.objects.create_user(
        username=username,
        password="clave-de-prueba-123",
        nombre_completo=username,
        rol=rol,
        **extra,
    )


@pytest.fixture
def admin(db):
    return _crear("admin", Rol.ADMINISTRADOR, is_staff=True)


@pytest.fixture
def cajera_alta(db):
    return _crear("cajera_alta", Rol.CAJERA, puede_crear_productos=True)


@pytest.fixture
def cajera(db):
    return _crear("cajera", Rol.CAJERA)


@pytest.fixture
def duenio(db):
    return _crear("duenio", Rol.DUENIO)
