"""Anulación de ventas (DEC-45, DEC-66 a DEC-73, CP-85)."""

from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.caja.models import (
    ConceptoMovimientoCaja,
    EstadoCaja,
    MedioPago,
    MovimientoCaja,
    TipoMovimientoCaja,
    Turno,
)
from apps.caja.services import (
    abrir_caja,
    cerrar_caja,
    registrar_egreso_otro,
    resumen_de_cierre,
)
from apps.catalogo.models import Producto, UnidadMedida
from apps.catalogo.services import crear_producto
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import EstadoVenta, Venta
from apps.ventas.services import anular_venta, registrar_venta, resumen_del_dia

pytestmark = pytest.mark.django_db

LISTA = reverse("ventas:lista")


def _crear(username, rol):
    return Usuario.objects.create_user(
        username=username,
        password="clave-de-prueba-123",
        nombre_completo=username.capitalize(),
        rol=rol,
    )


@pytest.fixture
def admin(db):
    return _crear("admin", Rol.ADMINISTRADOR)


@pytest.fixture
def duenio(db):
    return _crear("duenio", Rol.DUENIO)


@pytest.fixture
def tarjeta(db):
    return MedioPago.objects.create(nombre="Tarjeta")


@pytest.fixture
def caja_hoy(usuario, efectivo):
    return abrir_caja(usuario, Turno.MANANA, Decimal("5000.00"))


@pytest.fixture
def aceite(producto):
    producto.stock_actual = Decimal("10")
    producto.save()
    return producto


@pytest.fixture
def asado(categoria):
    return Producto.objects.create(
        nombre="Asado",
        categoria=categoria,
        precio_venta=Decimal("9500.00"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=False,
    )


@pytest.fixture
def venta_efectivo(usuario, caja_hoy, efectivo, aceite, asado):
    """$ 19.250 en efectivo: 2 aceites ($ 5.000) y 1,5 kg de asado ($ 14.250)."""
    venta, _ = registrar_venta(
        usuario, [(aceite.pk, Decimal("2")), (asado.pk, Decimal("1.5"))], efectivo
    )
    return venta


def _esperados(caja):
    return {medio.nombre: esperado for medio, esperado in resumen_de_cierre(caja)}


# Servicio (CP-85)


def test_cp85_anular_revierte_caja_y_stock_en_una_operacion(
    admin, caja_hoy, venta_efectivo, aceite, asado, efectivo
):
    assert venta_efectivo.monto_total == Decimal("19250.00")
    assert _esperados(caja_hoy)["Efectivo"] == Decimal("24250.00")

    venta = anular_venta(admin, venta_efectivo, "  Se cobró dos veces  ")

    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.ANULADA
    assert venta.anulada_por_usuario == admin
    assert venta.anulada_en is not None
    assert venta.motivo_anulacion == "Se cobró dos veces"
    reversa = MovimientoCaja.objects.get(venta=venta, concepto=ConceptoMovimientoCaja.ANULACION)
    assert reversa.tipo == TipoMovimientoCaja.EGRESO
    assert reversa.monto == Decimal("19250.00")
    assert reversa.medio_pago == efectivo
    assert reversa.caja == caja_hoy
    assert reversa.usuario == admin
    assert reversa.descripcion == "Se cobró dos veces"
    aceite.refresh_from_db()
    asado.refresh_from_db()
    assert aceite.stock_actual == Decimal("10")  # vuelve a sumar 2 (RI-07)
    assert asado.stock_actual == Decimal("0")  # sin control de stock, no cambia (DEC-36)


def test_la_venta_y_su_ingreso_no_se_modifican(admin, venta_efectivo):
    ingreso = MovimientoCaja.objects.get(venta=venta_efectivo, concepto="VENTA")
    detalles = list(venta_efectivo.detalleventa_set.values_list("cantidad", "subtotal"))

    anular_venta(admin, venta_efectivo, "Error de carga")

    venta_efectivo.refresh_from_db()
    assert venta_efectivo.monto_total == Decimal("19250.00")
    assert list(venta_efectivo.detalleventa_set.values_list("cantidad", "subtotal")) == detalles
    assert MovimientoCaja.objects.get(pk=ingreso.pk).monto == Decimal("19250.00")


def test_cp07_el_cierre_descuenta_la_anulacion_por_medio(
    usuario, admin, caja_hoy, venta_efectivo, efectivo, tarjeta, aceite
):
    venta_tarjeta, _ = registrar_venta(usuario, [(aceite.pk, Decimal("1"))], tarjeta)
    registrar_egreso_otro(usuario, Decimal("2000.00"), "Retiro")
    assert _esperados(caja_hoy) == {
        "Efectivo": Decimal("22250.00"),
        "Tarjeta": Decimal("2500.00"),
    }

    anular_venta(admin, venta_efectivo, "Error de carga")
    anular_venta(admin, venta_tarjeta, "Pagó con otra tarjeta")

    assert _esperados(caja_hoy) == {"Efectivo": Decimal("3000.00"), "Tarjeta": Decimal("0.00")}
    # Y la caja cierra contando eso, sin diferencias ni motivo.
    medios = {m.nombre: m.pk for m in MedioPago.objects.all()}
    cerrar_caja(usuario, {medios["Efectivo"]: Decimal("3000"), medios["Tarjeta"]: Decimal("0")})
    caja_hoy.refresh_from_db()
    assert caja_hoy.estado == EstadoCaja.CERRADA
    assert caja_hoy.observacion_cierre == ""


def _sin_cambios(venta, stock_aceite):
    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.CONFIRMADA
    assert not MovimientoCaja.objects.filter(concepto=ConceptoMovimientoCaja.ANULACION).exists()
    assert Producto.objects.get(nombre="Aceite 1 l").stock_actual == stock_aceite


@pytest.mark.parametrize("motivo", ["", "   ", None])
def test_dec66_sin_motivo_no_se_anula(admin, venta_efectivo, motivo):
    with pytest.raises(ValidationError) as error:
        anular_venta(admin, venta_efectivo, motivo)

    assert error.value.message_dict == {"motivo": ["Escribí por qué se anula la venta."]}
    _sin_cambios(venta_efectivo, Decimal("8"))


def test_una_venta_anulada_no_se_vuelve_a_anular(admin, venta_efectivo):
    anular_venta(admin, venta_efectivo, "Error de carga")

    with pytest.raises(ValidationError, match="ya está anulada"):
        anular_venta(admin, venta_efectivo, "Otra vez")

    assert MovimientoCaja.objects.filter(concepto=ConceptoMovimientoCaja.ANULACION).count() == 1
    assert Producto.objects.get(nombre="Aceite 1 l").stock_actual == Decimal("10")


def test_cp05_con_la_caja_cerrada_no_se_anula(usuario, admin, caja_hoy, venta_efectivo):
    cerrar_caja(
        usuario,
        {m.pk: e for m, e in resumen_de_cierre(caja_hoy)},
    )

    with pytest.raises(ValidationError, match="está cerrada"):
        anular_venta(admin, venta_efectivo, "Error de carga")

    _sin_cambios(venta_efectivo, Decimal("8"))


def test_dec69_sin_efectivo_suficiente_no_se_anula(usuario, admin, caja_hoy, venta_efectivo):
    registrar_egreso_otro(usuario, Decimal("20000.00"), "Retiro de los dueños")

    with pytest.raises(ValidationError, match="no alcanza"):
        anular_venta(admin, venta_efectivo, "Error de carga")

    _sin_cambios(venta_efectivo, Decimal("8"))


def test_dec72_se_anula_en_una_caja_abierta_de_otro_dia(usuario, admin, caja, efectivo, producto):
    venta = Venta.objects.create(
        caja=caja, usuario=usuario, medio_pago=efectivo, monto_total=Decimal("2500.00")
    )
    MovimientoCaja.objects.create(
        caja=caja,
        tipo=TipoMovimientoCaja.INGRESO,
        monto=Decimal("2500.00"),
        medio_pago=efectivo,
        concepto=ConceptoMovimientoCaja.VENTA,
        venta=venta,
        usuario=usuario,
    )

    anular_venta(admin, venta, "Error de carga")

    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.ANULADA


def _stocks(*productos):
    return {p.nombre: Producto.objects.get(pk=p.pk).stock_actual for p in productos}


def test_cp85_el_stock_vuelve_exactamente_al_valor_previo(
    usuario, admin, caja_hoy, efectivo, categoria, aceite, asado
):
    """Varias líneas: por unidad, por kg con decimales, un producto creado durante la venta
    y uno sin control de stock, que no se toca (RI-07, DEC-36, DEC-70)."""
    queso = Producto.objects.create(
        nombre="Queso por kg",
        categoria=categoria,
        precio_venta=Decimal("14300.00"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=True,
        stock_actual=Decimal("3.250"),
    )
    cajera_alta = _crear("cajera_alta", Rol.CAJERA)
    cajera_alta.puede_crear_productos = True
    cajera_alta.save()
    nuevo = crear_producto(  # CU-01 A1: arranca con stock 0
        cajera_alta,
        {
            "nombre": "Matambre de cerdo",
            "precio_venta": Decimal("8500.00"),
            "unidad_medida": UnidadMedida.KG,
            "controla_stock": True,
        },
    )
    productos = (aceite, queso, asado, nuevo)
    antes = _stocks(*productos)
    assert antes == {
        "Aceite 1 l": Decimal("10"),
        "Queso por kg": Decimal("3.250"),
        "Asado": Decimal("0"),
        "Matambre de cerdo": Decimal("0"),
    }

    venta, _ = registrar_venta(
        cajera_alta,
        [
            (aceite.pk, Decimal("3")),
            (queso.pk, Decimal("1.235")),
            (asado.pk, Decimal("2.5")),
            (nuevo.pk, Decimal("0.750")),
        ],
        efectivo,
    )
    assert _stocks(*productos) == {
        "Aceite 1 l": Decimal("7"),
        "Queso por kg": Decimal("2.015"),
        "Asado": Decimal("0"),
        "Matambre de cerdo": Decimal("-0.750"),
    }

    anular_venta(admin, venta, "Error de carga")

    assert _stocks(*productos) == antes

    # Una segunda anulación se rechaza y no devuelve stock otra vez.
    with pytest.raises(ValidationError, match="ya está anulada"):
        anular_venta(admin, venta, "Otra vez")
    assert _stocks(*productos) == antes
    assert MovimientoCaja.objects.filter(concepto=ConceptoMovimientoCaja.ANULACION).count() == 1


def test_dec70_devuelve_stock_aunque_el_producto_este_dado_de_baja(admin, venta_efectivo, aceite):
    Producto.objects.filter(pk=aceite.pk).update(activo=False)

    anular_venta(admin, venta_efectivo, "Error de carga")

    assert Producto.objects.get(pk=aceite.pk).stock_actual == Decimal("10")


@pytest.mark.parametrize("rol", [Rol.CAJERA, Rol.DUENIO])
def test_dec45_solo_el_administrador_anula(rol, venta_efectivo):
    with pytest.raises(PermissionDenied):
        anular_venta(_crear("otro", rol), venta_efectivo, "Error de carga")

    _sin_cambios(venta_efectivo, Decimal("8"))


def test_rnf10_la_anulacion_bloquea_la_caja_y_la_venta(admin, venta_efectivo):
    with CaptureQueriesContext(connection) as consultas:
        anular_venta(admin, venta_efectivo, "Error de carga")

    bloqueos = [q["sql"] for q in consultas.captured_queries if "FOR UPDATE" in q["sql"]]
    assert 'FROM "caja"' in bloqueos[0]
    assert any('FROM "venta"' in sql for sql in bloqueos[1:])


def test_dec73_el_resumen_del_dia_no_cuenta_las_anuladas(
    usuario, admin, venta_efectivo, efectivo, aceite
):
    registrar_venta(usuario, [(aceite.pk, Decimal("1"))], efectivo)

    anular_venta(admin, venta_efectivo, "Error de carga")

    assert resumen_del_dia(timezone.localdate()) == (1, Decimal("2500.00"))


# Integridad (DEC-67, DEC-68)


def test_dec67_la_base_exige_los_datos_de_anulacion_segun_el_estado(venta, admin):
    with pytest.raises(IntegrityError), transaction.atomic():
        Venta.objects.filter(pk=venta.pk).update(estado=EstadoVenta.ANULADA)
    with pytest.raises(IntegrityError), transaction.atomic():
        Venta.objects.filter(pk=venta.pk).update(motivo_anulacion="Sin anular")
    with pytest.raises(IntegrityError), transaction.atomic():
        Venta.objects.filter(pk=venta.pk).update(
            estado=EstadoVenta.ANULADA, anulada_en=timezone.now(), anulada_por_usuario=admin
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Venta.objects.filter(pk=venta.pk).update(estado="BORRADA")


def _reversa(una_venta, **cambios):
    datos = {
        "caja": una_venta.caja,
        "tipo": TipoMovimientoCaja.EGRESO,
        "monto": una_venta.monto_total,
        "medio_pago": una_venta.medio_pago,
        "concepto": ConceptoMovimientoCaja.ANULACION,
        "venta": una_venta,
        "usuario": una_venta.usuario,
    }
    datos.update(cambios)
    return MovimientoCaja.objects.create(**datos)


def test_dec68_la_anulacion_es_un_egreso_con_su_venta_y_una_sola(venta):
    with pytest.raises(IntegrityError), transaction.atomic():
        _reversa(venta, tipo=TipoMovimientoCaja.INGRESO)
    with pytest.raises(IntegrityError), transaction.atomic():
        _reversa(venta, venta=None)
    _reversa(venta)
    with pytest.raises(IntegrityError), transaction.atomic():
        _reversa(venta)


# Pantallas (DEC-71, DEC-73)


def test_dec71_el_administrador_ve_las_ventas_de_la_caja_abierta(client, admin, venta_efectivo):
    client.force_login(admin)

    respuesta = client.get(LISTA)

    assert respuesta.status_code == 200
    assert respuesta.context["ventas"] == [venta_efectivo]
    assert reverse("ventas:detalle", args=[venta_efectivo.pk]) in respuesta.content.decode()


def test_sin_caja_abierta_la_lista_lo_dice(client, admin):
    client.force_login(admin)

    assert "No hay una caja abierta." in client.get(LISTA).content.decode()


def test_el_administrador_anula_desde_el_detalle(client, admin, venta_efectivo):
    client.force_login(admin)
    detalle = reverse("ventas:detalle", args=[venta_efectivo.pk])
    assert "Anular venta" in client.get(detalle).content.decode()

    respuesta = client.post(
        reverse("ventas:anular", args=[venta_efectivo.pk]), {"motivo": "Se cobró dos veces"}
    )

    assert respuesta.status_code == 302
    assert respuesta["Location"] == detalle
    contenido = client.get(detalle).content.decode()
    assert "Anulada el" in contenido
    assert "Motivo: Se cobró dos veces" in contenido
    assert "Anular venta</button>" not in contenido


def test_sin_motivo_la_pantalla_muestra_el_error(client, admin, venta_efectivo):
    client.force_login(admin)

    respuesta = client.post(reverse("ventas:anular", args=[venta_efectivo.pk]), {"motivo": ""})

    assert respuesta.status_code == 400
    assert "Escribí por qué se anula la venta." in respuesta.content.decode()
    venta_efectivo.refresh_from_db()
    assert venta_efectivo.estado == EstadoVenta.CONFIRMADA


def test_un_error_del_servicio_se_muestra_en_el_detalle(client, usuario, admin, venta_efectivo):
    registrar_egreso_otro(usuario, Decimal("20000.00"), "Retiro")
    client.force_login(admin)

    respuesta = client.post(
        reverse("ventas:anular", args=[venta_efectivo.pk]), {"motivo": "Error de carga"}
    )

    assert respuesta.status_code == 400
    assert "no alcanza" in respuesta.content.decode()


@pytest.mark.parametrize("quien", ["cajera", "duenio"])
def test_cajera_y_duenios_no_entran_a_la_anulacion(client, quien, usuario, duenio, venta_efectivo):
    client.force_login(usuario if quien == "cajera" else duenio)

    assert client.get(LISTA).status_code == 403
    assert client.get(reverse("ventas:detalle", args=[venta_efectivo.pk])).status_code == 403
    respuesta = client.post(
        reverse("ventas:anular", args=[venta_efectivo.pk]), {"motivo": "Error de carga"}
    )
    assert respuesta.status_code == 403
    venta_efectivo.refresh_from_db()
    assert venta_efectivo.estado == EstadoVenta.CONFIRMADA


def test_sin_sesion_la_anulacion_lleva_al_ingreso(client, venta_efectivo):
    respuesta = client.get(LISTA)

    assert respuesta.status_code == 302
    assert reverse("usuarios:ingresar") in respuesta["Location"]


def test_dec73_el_ticket_muestra_la_venta_anulada(client, usuario, admin, venta_efectivo):
    anular_venta(admin, venta_efectivo, "Error de carga")
    client.force_login(usuario)

    contenido = client.get(reverse("ventas:ticket", args=[venta_efectivo.pk])).content.decode()

    assert "ANULADA el" in contenido
    assert "Motivo: Error de carga" in contenido


# Revisión de H2 (M4, M5)


def test_el_motivo_admite_hasta_255_caracteres(admin, venta_efectivo):
    with pytest.raises(ValidationError) as error:
        anular_venta(admin, venta_efectivo, "x" * 256)
    assert error.value.message_dict == {"motivo": ["El motivo admite hasta 255 caracteres."]}
    _sin_cambios(venta_efectivo, Decimal("8"))

    anular_venta(admin, venta_efectivo, "y" * 255)

    reversa = MovimientoCaja.objects.get(concepto=ConceptoMovimientoCaja.ANULACION)
    assert reversa.descripcion == "y" * 255


def test_sin_motivo_el_detalle_no_pide_confirmacion_antes_del_error(client, admin, venta_efectivo):
    client.force_login(admin)

    contenido = client.get(reverse("ventas:detalle", args=[venta_efectivo.pk])).content.decode()

    # Con el motivo vacío el formulario se envía sin confirmar y el servidor muestra el error.
    assert "onsubmit=\"return this.motivo.value.trim() === '' || confirm(" in contenido


# DEC-77: el cierre y su reporte listan las ventas anuladas (M2)


def test_dec77_el_cierre_y_su_reporte_listan_las_ventas_anuladas(
    client, usuario, admin, caja_hoy, venta_efectivo, efectivo
):
    anular_venta(admin, venta_efectivo, "Se cobró dos veces")
    client.force_login(usuario)

    cerrar = client.get(reverse("caja:cerrar")).content.decode()
    respuesta = client.post(
        reverse("caja:cerrar"), {f"contado_{efectivo.pk}": "5000.00", "observacion": ""}
    )
    reporte = client.get(respuesta["Location"]).content.decode()

    for contenido in (cerrar, reporte):
        assert "Ventas anuladas" in contenido
        assert f"Venta N.º {venta_efectivo.pk} · Se cobró dos veces" in contenido
        assert "$ 19.250,00 Efectivo" in contenido


def test_dec77_sin_anulaciones_el_cierre_no_muestra_la_lista(client, usuario, venta_efectivo):
    client.force_login(usuario)

    assert "Ventas anuladas" not in client.get(reverse("caja:cerrar")).content.decode()


# Revisión de H2 (M6)


def test_con_la_caja_cerrada_el_detalle_no_ofrece_anular(
    client, usuario, admin, caja_hoy, venta_efectivo
):
    cerrar_caja(usuario, {m.pk: e for m, e in resumen_de_cierre(caja_hoy)})
    client.force_login(admin)

    contenido = client.get(reverse("ventas:detalle", args=[venta_efectivo.pk])).content.decode()

    assert "La caja de esta venta está cerrada: ya no se puede anular." in contenido
    assert "Anular venta</button>" not in contenido


def test_dec73_las_ultimas_ventas_del_inicio_marcan_la_anulada(client, admin, venta_efectivo):
    anular_venta(admin, venta_efectivo, "Error de carga")
    client.force_login(admin)

    contenido = client.get(reverse("inicio")).content.decode()

    assert "Anulada</span>" in contenido
    assert "line-through" in contenido
