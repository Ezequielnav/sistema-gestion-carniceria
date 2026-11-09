"""CU-05 en un navegador real: el buscador de productos del ingreso, respaldo del buscador común
(L13, DEC-181). Correr aparte con `pytest -m navegador`."""

import re
from decimal import Decimal

import pytest
from playwright.sync_api import expect

from apps.proveedores.models import IngresoMercaderia
from apps.proveedores.services import registrar_ingreso
from apps.usuarios.models import Rol, Usuario

pytestmark = [pytest.mark.navegador, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        username="admin_navegador",
        password="clave-de-prueba-123",
        nombre_completo="Admin de prueba",
        rol=Rol.ADMINISTRADOR,
    )


def test_buscador_del_ingreso_filtra_elige_y_completa_el_precio(
    navegador, admin, proveedor, producto
):
    producto.plus_interno = "501"
    producto.save()
    # Un ingreso anterior deja el último precio de compra con este proveedor (DEC-90).
    registrar_ingreso(admin, proveedor, [(producto.pk, Decimal("1"), Decimal("1800"))])
    pagina = navegador.entrar(admin)
    pagina.goto(navegador.url_de("/proveedores/ingresos/nuevo/"))
    pagina.locator("#id_proveedor").select_option(str(proveedor.pk))
    buscar = pagina.locator("#buscar")

    # Sin texto no se abre la lista; Enter con un código filtra y no agrega (en la venta, sí).
    buscar.click()
    expect(pagina.locator("#resultados")).to_be_hidden()
    buscar.press_sequentially("501", delay=80)
    buscar.press("Enter")
    opciones = pagina.locator("#resultados [role=option]")
    expect(opciones).to_have_count(1)
    expect(opciones.first).to_contain_text("Último: $ 1.800,00 / u.")
    expect(pagina.locator("#lineas tr")).to_have_count(0)

    # Flechas y Enter eligen; el cursor queda en la cantidad.
    buscar.press("ArrowDown")
    buscar.press("Enter")
    expect(pagina.get_by_label("Cantidad de Aceite 1 l")).to_be_focused()
    expect(pagina.get_by_label("Precio de compra de Aceite 1 l")).to_have_value("1800.00")
    pagina.keyboard.type("3")
    expect(pagina.locator("#total")).to_have_text("$ 5.400,00")

    # Borrar el texto cierra la lista; un texto sin resultados lo dice.
    buscar.press_sequentially("zzz", delay=80)
    expect(pagina.locator("#resultados")).to_contain_text("No se encontraron productos.")
    buscar.fill("")
    expect(pagina.locator("#resultados")).to_be_hidden()

    pagina.locator("#confirmar").click()
    expect(pagina).to_have_url(re.compile(r"/proveedores/ingresos/\d+/$"))
    assert IngresoMercaderia.objects.count() == 2
