"""DEC-202 en el navegador: el ojo muestra y oculta la contraseña, y se oculta al enviar.
Correr aparte con `pytest -m navegador`."""

import pytest

pytestmark = [pytest.mark.navegador, pytest.mark.django_db(transaction=True)]


def test_dec202_el_ojo_muestra_y_oculta_la_contrasena(navegador):
    pagina = navegador
    pagina.goto(pagina.url_de("/ingresar/"))
    campo = pagina.locator("#id_password")
    ojo = pagina.get_by_role("button", name="Mostrar contraseña")
    campo.fill("clave-de-ejemplo")

    ojo.click()
    assert campo.get_attribute("type") == "text"
    ocultar = pagina.get_by_role("button", name="Ocultar contraseña")
    assert ocultar.get_attribute("aria-pressed") == "true"

    ocultar.click()
    assert campo.get_attribute("type") == "password"


def test_dec202_al_enviar_la_contrasena_vuelve_a_ocultarse(navegador):
    pagina = navegador
    pagina.goto(pagina.url_de("/ingresar/"))
    pagina.fill("#id_username", "nadie")
    pagina.fill("#id_password", "clave-de-ejemplo")
    pagina.get_by_role("button", name="Mostrar contraseña").click()

    # Se frena el envío para mirar el campo justo después del submit.
    pagina.evaluate(
        "document.querySelector('form').addEventListener('submit', e => e.preventDefault())"
    )
    pagina.get_by_role("button", name="Ingresar", exact=True).click()

    assert pagina.locator("#id_password").get_attribute("type") == "password"
