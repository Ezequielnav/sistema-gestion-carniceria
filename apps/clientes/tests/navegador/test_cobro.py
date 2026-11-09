"""CU-04 en un navegador real: la cajera cobra y llega al comprobante (CP-147, CP-152; L16,
DEC-185). Correr aparte con `pytest -m navegador`."""

import re
from decimal import Decimal

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from apps.caja.models import Turno
from apps.caja.services import abrir_caja
from apps.clientes.models import (
    MovimientoCuentaCorriente,
    PagoCliente,
    TipoMovimientoCuentaCorriente,
)

pytestmark = [pytest.mark.navegador, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def deudor(cliente):
    """Un cliente que debe $ 1.000 (saldo inicial, DEC-119)."""
    cliente.nombre = "Marta Gómez"
    cliente.save()
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        tipo=TipoMovimientoCuentaCorriente.SALDO_INICIAL,
        monto=Decimal("1000.00"),
        fecha_origen=timezone.localdate(),
        motivo="Deuda anterior",
    )
    return cliente


def test_cp152_la_cajera_cobra_y_llega_al_comprobante(navegador, usuario, efectivo, deudor):
    abrir_caja(usuario, Turno.MANANA)
    pagina = navegador.entrar(usuario)
    pagina.goto(navegador.url_de("/clientes/cobrar/"))

    # SC-01: escribir, elegir con flechas y Enter.
    pagina.locator("#buscar-cliente").press_sequentially("Marta", delay=80)
    expect(pagina.locator("#clientes [role=option]")).to_have_count(1)
    pagina.keyboard.press("ArrowDown")
    pagina.keyboard.press("Enter")
    expect(pagina.locator("#cliente-nombre")).to_have_text("Marta Gómez")
    expect(pagina.locator("#cliente-saldo")).to_contain_text("1.000,00")

    pagina.get_by_label("Monto").fill("300")
    pagina.get_by_label("Medio de pago").select_option(str(efectivo.pk))
    pagina.get_by_role("button", name="Registrar cobro").click()

    cobro = PagoCliente.objects.get()
    expect(pagina).to_have_url(re.compile(rf"/clientes/cobros/{cobro.pk}/comprobante/$"))
    comprobante = pagina.get_by_label("Comprobante de cobro")
    expect(comprobante).to_contain_text(f"Comprobante de cobro N.º {cobro.pk}")
    expect(comprobante).to_contain_text("Marta Gómez")
    expect(comprobante).to_contain_text("$ 1.000,00")  # saldo anterior
    expect(comprobante).to_contain_text("$ 700,00")  # saldo posterior
    expect(pagina.get_by_role("button", name="Imprimir")).to_be_visible()

    # Desde "Nuevo cobro" vuelve a la pantalla, donde puede reimprimirlo (DEC-185).
    pagina.get_by_role("link", name="Nuevo cobro").click()
    pagina.get_by_role("link", name=f"Comprobante del cobro N.º {cobro.pk}").click()
    expect(pagina.get_by_label("Comprobante de cobro")).to_contain_text("$ 700,00")
