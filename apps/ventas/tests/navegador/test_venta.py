"""CU-01 en un navegador real (L2, DEC-160, DEC-180): la unión de venta.js con lector.js y
buscador.js (CP-150), el tope de líneas (CP-141, L5) y el aviso de stock al retomar una venta
guardada (CP-145, L11). Correr aparte con `pytest -m navegador`."""

import json
import re
from decimal import Decimal

import pytest
from playwright.sync_api import expect

from apps.caja.models import Turno
from apps.caja.services import abrir_caja
from apps.catalogo.models import Producto, UnidadMedida
from apps.ventas.models import DetalleVenta, Venta
from apps.ventas.services import LINEAS_MAXIMAS, MENSAJE_LINEAS_MAXIMAS

pytestmark = [pytest.mark.navegador, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def caja_hoy(usuario, efectivo):
    return abrir_caja(usuario, Turno.MANANA)


@pytest.fixture
def aceite(producto):
    producto.plus_interno = "501"
    producto.stock_actual = Decimal("10")
    producto.save()
    return producto


@pytest.fixture
def queso(categoria):
    return Producto.objects.create(
        nombre="Queso cremoso",
        categoria=categoria,
        plus_interno="205",
        precio_venta=Decimal("8000.00"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=False,
    )


def _venta_nueva(navegador, usuario):
    pagina = navegador.entrar(usuario)
    pagina.goto(navegador.url_de("/ventas/nueva/"))
    expect(pagina.locator("#buscar")).to_be_focused()
    return pagina


def _lineas(pagina):
    return pagina.locator("#lineas tr")


# CP-150: venta completa con lector, buscador, confirmación y ticket


def test_cp150_venta_completa_con_lector_buscador_y_ticket(
    navegador, usuario, caja_hoy, efectivo, aceite, queso
):
    pagina = _venta_nueva(navegador, usuario)

    # El lector escribe el código muy rápido y termina con Enter (DEC-37): agrega el aceite.
    pagina.keyboard.type("501\n")
    expect(_lineas(pagina)).to_have_count(1)
    # Otra lectura del mismo código suma en la misma línea (DEC-53).
    pagina.keyboard.type("501\n")
    expect(_lineas(pagina)).to_have_count(1)
    expect(pagina.get_by_label("Cantidad de Aceite 1 l")).to_have_value("2")

    # Buscador: escribir, elegir con flechas y Enter (DEC-97). Por kg, el cursor va al peso.
    pagina.locator("#buscar").press_sequentially("Queso", delay=80)
    expect(pagina.locator("#resultados [role=option]")).to_have_count(1)
    pagina.keyboard.press("ArrowDown")
    pagina.keyboard.press("Enter")
    peso = pagina.get_by_label("Cantidad de Queso cremoso")
    expect(peso).to_be_focused()
    # Una persona teclea más lento que el lector (DEC-75).
    peso.press_sequentially("0.5", delay=120)
    pagina.wait_for_timeout(200)
    # Una lectura en el campo del peso se busca como producto y no cambia el peso (DEC-75).
    pagina.keyboard.type("501\n")
    expect(peso).to_have_value("0.5")
    expect(pagina.get_by_label("Cantidad de Aceite 1 l")).to_have_value("3")
    expect(pagina.locator("#total")).to_have_text("$ 11.500,00")

    pagina.locator("#id_medio_pago").select_option(str(efectivo.pk))
    pagina.locator("#confirmar").click()

    expect(pagina).to_have_url(re.compile(r"/ventas/\d+/ticket/$"))
    ticket = pagina.get_by_label("Ticket")
    expect(ticket).to_contain_text("Aceite 1 l")
    expect(ticket).to_contain_text("Queso cremoso")
    expect(ticket).to_contain_text("$ 11.500,00")
    expect(ticket).to_contain_text("No válido como factura")
    venta = Venta.objects.get()
    assert venta.monto_total == Decimal("11500.00")
    assert DetalleVenta.objects.filter(venta=venta).count() == 2
    aceite.refresh_from_db()
    assert aceite.stock_actual == Decimal("7")


def test_cp150_sin_caja_abierta_avisa_y_no_ofrece_vender(navegador, usuario):
    pagina = navegador.entrar(usuario)
    pagina.goto(navegador.url_de("/ventas/nueva/"))

    expect(pagina.get_by_role("link", name="Ir a Caja")).to_be_visible()


# Venta guardada en la pestaña (DEC-47): se arma como la guarda venta_guardada.js.


def _guardar_venta(pagina, usuario, lineas):
    clave = f"venta-en-curso-{usuario.pk}"
    datos = json.dumps({"lineas": lineas, "medio": "", "cliente": None})
    pagina.evaluate("([clave, datos]) => sessionStorage.setItem(clave, datos)", [clave, datos])
    pagina.reload()


def _linea(producto, cantidad, stock):
    return {
        "producto": {
            "id": producto.pk,
            "nombre": producto.nombre,
            "plus": producto.plus_interno or "",
            "precio": str(producto.precio_venta),
            "unidad": producto.unidad_medida,
            "stock": stock,
        },
        "cantidad": cantidad,
    }


# CP-141 en pantalla: el formulario no agrega la línea 51 (L5, DEC-173)


def test_cp141_el_formulario_no_agrega_la_linea_51(navegador, usuario, caja_hoy, categoria):
    productos = Producto.objects.bulk_create(
        Producto(
            nombre=f"Producto {i:02d}",
            categoria=categoria,
            plus_interno=str(700 + i),
            precio_venta=Decimal("100.00"),
            unidad_medida=UnidadMedida.UNIDAD,
            controla_stock=False,
        )
        for i in range(LINEAS_MAXIMAS + 1)
    )
    pagina = _venta_nueva(navegador, usuario)
    _guardar_venta(pagina, usuario, [_linea(p, "1", None) for p in productos[:LINEAS_MAXIMAS]])
    expect(_lineas(pagina)).to_have_count(LINEAS_MAXIMAS)

    pagina.locator("#buscar").focus()
    pagina.keyboard.type(f"{productos[-1].plus_interno}\n")

    expect(pagina.locator("#errores")).to_have_text(MENSAJE_LINEAS_MAXIMAS)
    expect(_lineas(pagina)).to_have_count(LINEAS_MAXIMAS)
    # Sumar a una línea que ya está sigue funcionando.
    pagina.keyboard.type(f"{productos[0].plus_interno}\n")
    expect(pagina.get_by_label(f"Cantidad de {productos[0].nombre}")).to_have_value("2")


# CP-145 en pantalla: el aviso usa el stock actual al retomar (L11, DEC-176)


def test_cp145_al_retomar_avisa_con_el_stock_actual(navegador, usuario, caja_hoy, aceite):
    aceite.stock_actual = Decimal("3")
    aceite.save()
    pagina = _venta_nueva(navegador, usuario)

    # Guardada cuando había 100: con ese dato viejo no avisaría.
    _guardar_venta(pagina, usuario, [_linea(aceite, "5", "100.000")])

    expect(pagina.locator(".aviso-stock")).to_have_text(
        "Stock insuficiente: disponible 3. Se puede vender igual."
    )


def test_cp145_al_retomar_no_avisa_si_el_stock_actual_alcanza(navegador, usuario, caja_hoy, aceite):
    pagina = _venta_nueva(navegador, usuario)

    # Guardada cuando no había stock: hoy hay 10 y alcanza.
    with pagina.expect_response(re.compile(r"/ventas/stock/\?ids=")):
        _guardar_venta(pagina, usuario, [_linea(aceite, "5", "0.000")])

    expect(_lineas(pagina)).to_have_count(1)
    expect(pagina.locator(".aviso-stock")).to_be_hidden()
    expect(pagina.get_by_label("Cantidad de Aceite 1 l")).to_have_value("5")


def test_cp150_la_lista_se_abre_a_pedido_y_se_cierra_con_escape(
    navegador, usuario, caja_hoy, aceite, queso
):
    pagina = _venta_nueva(navegador, usuario)
    opciones = pagina.locator("#resultados [role=option]")

    # Clic en el buscador vacío: todos los activos (DEC-97).
    pagina.locator("#buscar").click()
    expect(opciones).to_have_count(2)
    pagina.keyboard.press("Escape")
    expect(pagina.locator("#resultados")).to_be_hidden()

    # "Ver productos" descarta lo escrito y muestra todos.
    pagina.locator("#buscar").fill("Ques")
    pagina.get_by_role("button", name="Ver productos").click()
    expect(opciones).to_have_count(2)
    expect(pagina.locator("#buscar")).to_have_value("")

    # Un texto sin resultados lo dice; la cajera sin permiso de alta no ve "Crear producto".
    pagina.locator("#buscar").press_sequentially("zzz", delay=80)
    expect(pagina.locator("#resultados")).to_contain_text("No se encontraron productos.")
    expect(pagina.get_by_role("button", name="Crear producto")).to_have_count(0)


def test_cp150_la_cajera_con_permiso_crea_el_producto_que_no_encuentra(
    navegador, usuario, caja_hoy
):
    usuario.puede_crear_productos = True
    usuario.save()
    pagina = _venta_nueva(navegador, usuario)

    pagina.locator("#buscar").press_sequentially("Matambre", delay=80)
    pagina.get_by_role("button", name="Crear producto").click()

    expect(pagina.locator("#alta-producto")).to_be_visible()
    expect(pagina.locator("#form-producto [name=producto-nombre]")).to_have_value("Matambre")
