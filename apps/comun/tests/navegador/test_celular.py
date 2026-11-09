"""RM-09 automatizado a 375 px (DEC-170, DEC-182 / S-11; L7). Recorre las pantallas de cada
rol con datos de nombres largos y verifica que la página no se desplace de costado y que todo
botón, enlace o campo visible quede dentro de la pantalla, salvo los que están en una tabla que
se desplaza dentro de su recuadro. En las pantallas de consulta y Reportes, además, cada tabla
se desplaza dentro de su recuadro. Correr aparte con `pytest -m navegador`."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.caja.models import MedioPago, Turno
from apps.caja.services import abrir_caja, cerrar_caja
from apps.catalogo.models import Categoria, Producto, UnidadMedida
from apps.clientes.models import (
    Cliente,
    MovimientoCuentaCorriente,
    TipoMovimientoCuentaCorriente,
)
from apps.clientes.services import registrar_cobro
from apps.proveedores.models import Proveedor
from apps.proveedores.services import registrar_ingreso, registrar_pago
from apps.usuarios.models import Rol, Usuario
from apps.ventas.services import registrar_venta

pytestmark = [pytest.mark.navegador, pytest.mark.django_db(transaction=True)]

CELULAR = {"width": 375, "height": 812}

# Qué hay fuera de lugar a 375 px: el desborde de la página y los controles visibles fuera de
# la pantalla que no están dentro de un recuadro con desplazamiento horizontal.
REVISAR = """() => {
  const ancho = window.innerWidth;
  const enRecuadro = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if ((o === "auto" || o === "scroll") && p.scrollWidth > p.clientWidth + 1) return true;
    }
    return false;
  };
  const fuera = [...document.querySelectorAll("a, button, input, select, textarea")]
    .filter((el) => el.type !== "hidden" && el.checkVisibility())
    .filter((el) => {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return false;
      return (r.left < -1 || r.right > ancho + 1) && !enRecuadro(el);
    })
    .map((el) => el.outerHTML.slice(0, 100));
  const tablasSueltas = [...document.querySelectorAll("table")]
    .filter((t) => t.checkVisibility())
    .filter((t) => {
      for (let p = t.parentElement; p; p = p.parentElement) {
        const o = getComputedStyle(p).overflowX;
        if (o === "auto" || o === "scroll") return false;
      }
      return t.getBoundingClientRect().right > ancho + 1;
    }).length;
  return { desborde: document.documentElement.scrollWidth - ancho, fuera, tablasSueltas };
}"""

LARGO = "Queso cremoso en barra de primera marca feteado especial"


def _crear(username, rol, **extra):
    return Usuario.objects.create_user(
        username=username,
        password="clave-de-prueba-123",
        nombre_completo=f"{username.title()} con un nombre bastante largo",
        rol=rol,
        **extra,
    )


@pytest.fixture
def escenario(db):
    """Datos ficticios con nombres largos y una caja cerrada y otra abierta."""
    admin = _crear("admin", Rol.ADMINISTRADOR)
    cajera = _crear("cajera", Rol.CAJERA, puede_crear_productos=True)
    duenio = _crear("duenio", Rol.DUENIO)
    efectivo = MedioPago.objects.create(nombre="Efectivo", es_efectivo=True)
    tarjeta = MedioPago.objects.create(nombre="Tarjeta de débito")
    categoria = Categoria.objects.create(nombre="Almacén y lácteos de primera")
    productos = [
        Producto.objects.create(
            nombre=f"{LARGO} {i}",
            categoria=categoria,
            plus_interno=str(9000 + i),
            precio_venta=Decimal("123456.78"),
            unidad_medida=UnidadMedida.KG if i % 2 else UnidadMedida.UNIDAD,
            controla_stock=True,
            stock_actual=Decimal("2"),
            stock_minimo=Decimal("5"),
        )
        for i in range(3)
    ]
    cliente = Cliente.objects.create(
        nombre="María de los Ángeles Fernández de la Torre", telefono="11 5555-5555"
    )
    MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        tipo=TipoMovimientoCuentaCorriente.SALDO_INICIAL,
        monto=Decimal("987654.32"),
        fecha_origen=timezone.localdate(),
        motivo="Deuda anterior de la libreta del mostrador",
    )
    proveedor = Proveedor.objects.create(nombre="Distribuidora Mayorista del Sur Hermanos SRL")
    ingreso = registrar_ingreso(
        admin, proveedor, [(productos[0].pk, Decimal("10"), Decimal("98765.43"))]
    )
    manana = abrir_caja(cajera, Turno.MANANA, Decimal("500000.00"))
    venta, _ = registrar_venta(cajera, [(p.pk, Decimal("1")) for p in productos], efectivo)
    cobro = registrar_cobro(cajera, cliente, Decimal("1000.00"), efectivo)
    pago = registrar_pago(admin, ingreso, Decimal("1000.00"), efectivo)
    cerrar_caja(
        cajera,
        {efectivo.pk: Decimal("870370.34"), tarjeta.pk: Decimal("0")},
        "Faltaron monedas en el cambio",
    )
    abrir_caja(cajera, Turno.TARDE, Decimal("1000.00"))
    # La cajera reimprime solo los comprobantes de la caja abierta de hoy (DEC-185).
    cobro_de_la_tarde = registrar_cobro(cajera, cliente, Decimal("500.00"), efectivo)
    return {
        "cobro_de_la_tarde": cobro_de_la_tarde,
        "admin": admin,
        "cajera": cajera,
        "duenio": duenio,
        "producto": productos[0],
        "cliente": cliente,
        "ingreso": ingreso,
        "pago": pago,
        "venta": venta,
        "cobro": cobro,
        "caja": manana,
    }


def _revisar(navegador, usuario, consultas, operacion):
    """Recorre las pantallas y devuelve las fallas: en todas, desborde y controles fuera; en
    las de consulta, además, tablas que no se desplazan dentro de su recuadro."""
    pagina = navegador.entrar(usuario)
    pagina.set_viewport_size(CELULAR)
    fallas = []
    for ruta, es_consulta in [(r, True) for r in consultas] + [(r, False) for r in operacion]:
        respuesta = pagina.goto(navegador.url_de(ruta))
        if not respuesta.ok:
            fallas.append(f"{ruta}: respondió {respuesta.status}")
            continue
        pagina.wait_for_load_state("networkidle")
        resultado = pagina.evaluate(REVISAR)
        if resultado["desborde"] > 1:
            fallas.append(f"{ruta}: la página se desplaza {resultado['desborde']} px de costado")
        for control in resultado["fuera"]:
            fallas.append(f"{ruta}: fuera de la pantalla: {control}")
        if es_consulta and resultado["tablasSueltas"]:
            fallas.append(f"{ruta}: tabla que no se desplaza dentro de su recuadro")
    return fallas


def test_rm09_administrador_a_375_px(navegador, escenario):
    e = escenario
    consultas = [
        "/",
        "/productos/",
        "/productos/?stock_bajo=1",
        "/productos/categorias/",
        "/productos/ajustes/",
        "/clientes/",
        f"/clientes/{e['cliente'].pk}/",
        f"/clientes/cobros/{e['cobro'].pk}/",
        f"/clientes/cobros/{e['cobro'].pk}/comprobante/",
        "/proveedores/",
        "/proveedores/ingresos/",
        f"/proveedores/ingresos/{e['ingreso'].pk}/",
        "/proveedores/pagos/",
        f"/proveedores/pagos/{e['pago'].pk}/",
        "/ventas/historial/?todas=on",
        f"/ventas/{e['venta'].pk}/",
        f"/ventas/{e['venta'].pk}/ticket/",
        f"/caja/{e['caja'].pk}/cierre/",
        "/caja/medios/",
        "/usuarios/",
        "/reportes/",
        "/reportes/ventas-diarias/",
        "/reportes/productos/",
        "/reportes/ingresos/",
        "/reportes/medios-de-pago/",
        "/reportes/cierres/",
    ]
    operacion = [
        "/clientes/cobrar/",
        "/clientes/nuevo/",
        f"/clientes/{e['cliente'].pk}/editar/",
        "/productos/nuevo/",
        f"/productos/{e['producto'].pk}/editar/",
        "/proveedores/nuevo/",
        "/proveedores/ingresos/nuevo/",
        "/proveedores/pagos/nuevo/",
        "/usuarios/nuevo/",
        "/caja/medios/nuevo/",
    ]

    fallas = _revisar(navegador, e["admin"], consultas, operacion)
    assert not fallas, "\n".join(fallas)


def test_rm09_cajera_a_375_px(navegador, escenario):
    e = escenario
    consultas = ["/", "/productos/", "/ventas/"]
    operacion = [
        "/ventas/nueva/",
        "/caja/",
        "/caja/cerrar/",
        "/clientes/cobrar/",
        f"/clientes/cobros/{e['cobro_de_la_tarde'].pk}/comprobante/",
        "/productos/nuevo/",
    ]

    fallas = _revisar(navegador, e["cajera"], consultas, operacion)
    assert not fallas, "\n".join(fallas)


def test_rm09_duenio_a_375_px(navegador, escenario):
    consultas = [
        "/",
        "/reportes/",
        "/reportes/ventas-diarias/",
        "/reportes/productos/",
        "/reportes/ingresos/",
        "/reportes/medios-de-pago/",
        "/reportes/cierres/",
        f"/caja/{escenario['caja'].pk}/cierre/",
    ]

    fallas = _revisar(navegador, escenario["duenio"], consultas, [])
    assert not fallas, "\n".join(fallas)


def test_rm09_el_menu_se_abre_en_el_celular(navegador, escenario):
    pagina = navegador.entrar(escenario["admin"])
    pagina.set_viewport_size(CELULAR)
    pagina.goto(navegador.url_de("/"))

    menu = pagina.locator("#menu-lateral")
    assert not menu.is_visible()
    pagina.get_by_role("button", name="Abrir menú").click()
    assert menu.get_by_role("link", name="Productos").is_visible()


def test_rm09_la_pestana_elegida_de_reportes_queda_a_la_vista(navegador, escenario):
    # RM-13: a 375 px la barra de pestañas se desplaza; la elegida tiene que verse.
    pagina = navegador.entrar(escenario["duenio"])
    pagina.set_viewport_size(CELULAR)

    for ruta in ["/reportes/ingresos/", "/reportes/medios-de-pago/", "/reportes/cierres/"]:
        pagina.goto(navegador.url_de(ruta))
        caja = pagina.locator("nav[aria-label=Reportes] [aria-current=page]").bounding_box()
        assert caja["x"] >= 0 and caja["x"] + caja["width"] <= CELULAR["width"], ruta
