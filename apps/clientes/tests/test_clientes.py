"""CU-12 Gestionar clientes y SC-01 Elegir cliente (H4, etapa 2).

CP-114; DEC-108, DEC-109, DEC-115 a DEC-118; S-1, S-2 y S-7 (DEC-120, DEC-121, DEC-126).
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, MovimientoCuentaCorriente, TipoMovimientoCuentaCorriente
from apps.clientes.services import (
    LIMITE_BUSQUEDA,
    buscar_para_elegir,
    crear_cliente,
    dar_de_baja,
    listar_clientes,
    modificar_cliente,
    reactivar,
)

pytestmark = pytest.mark.django_db

LISTADO = reverse("clientes:clientes")
NUEVO = reverse("clientes:nuevo")
BUSCAR = reverse("clientes:buscar")


def _editar(cliente):
    return reverse("clientes:editar", args=[cliente.pk])


def _baja(cliente):
    return reverse("clientes:baja", args=[cliente.pk])


def _reactivar(cliente):
    return reverse("clientes:reactivar", args=[cliente.pk])


def _deuda(cliente, monto, dias_atras=0):
    """Una deuda como la deja el saldo inicial (DEC-119), con su fecha de origen."""
    return MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        tipo=TipoMovimientoCuentaCorriente.SALDO_INICIAL,
        monto=Decimal(monto),
        fecha_origen=timezone.localdate() - datetime.timedelta(days=dias_atras),
        motivo="Deuda anterior",
    )


# Servicio


def test_cp114_alta_modificacion_baja_y_reactivacion(admin):
    cliente = crear_cliente(
        admin,
        {
            "nombre": "  Juan Pérez ",
            "telefono": " 381 555-0101 ",
            "direccion": "San Martín 123",
            "limite_credito": Decimal("50000"),
            "observaciones": "Paga a fin de mes",
        },
    )
    assert (cliente.nombre, cliente.telefono) == ("Juan Pérez", "381 555-0101")
    assert cliente.limite_credito == Decimal("50000") and cliente.activo

    modificar_cliente(admin, cliente, {"nombre": "Juan Pérez", "limite_credito": None})
    cliente.refresh_from_db()
    assert cliente.limite_credito is None and cliente.direccion == ""

    dar_de_baja(admin, cliente)
    assert list(listar_clientes(admin)) == []
    assert list(listar_clientes(admin, incluir_inactivos=True)) == [cliente]

    reactivar(admin, cliente)
    assert list(listar_clientes(admin)) == [cliente]


def test_dec117_solo_el_nombre_es_obligatorio(admin):
    cliente = crear_cliente(admin, {"nombre": "María Gómez"})

    assert (cliente.telefono, cliente.direccion, cliente.observaciones) == ("", "", "")
    assert cliente.limite_credito is None


@pytest.mark.parametrize(
    ("datos", "campo"),
    [
        ({"nombre": "   "}, "nombre"),
        ({"nombre": "X", "limite_credito": Decimal("-1")}, "limite_credito"),
        ({"nombre": "X", "limite_credito": Decimal("10.005")}, "limite_credito"),
        ({"nombre": "X", "limite_credito": Decimal("10000000000")}, "limite_credito"),
    ],
)
def test_cp114_datos_invalidos_se_rechazan(admin, datos, campo):
    with pytest.raises(ValidationError) as error:
        crear_cliente(admin, datos)

    assert campo in error.value.message_dict
    assert not Cliente.objects.exists()


def test_dec117_el_nombre_repetido_no_se_bloquea(admin, cliente):
    crear_cliente(admin, {"nombre": cliente.nombre})

    assert Cliente.objects.filter(nombre=cliente.nombre).count() == 2


def test_dec118_la_busqueda_va_por_nombre_o_telefono(admin, cliente):
    otro = crear_cliente(admin, {"nombre": "Comedor Los Álamos", "telefono": "381 555-0103"})

    assert list(listar_clientes(admin, "álamos")) == [otro]
    assert list(listar_clientes(admin, "0103")) == [otro]
    assert list(listar_clientes(admin, "prueba")) == [cliente]


def test_s7_solo_con_deuda_vencida(admin, cliente):
    vencido = Cliente.objects.create(nombre="Con deuda vieja")
    reciente = Cliente.objects.create(nombre="Con deuda nueva")
    _deuda(vencido, "1000", dias_atras=45)
    _deuda(reciente, "1000", dias_atras=5)

    assert list(listar_clientes(admin, solo_vencidos=True)) == [vencido]


@pytest.mark.parametrize("quien", ["cajera_alta", "cajera", "duenio"])
def test_dec116_la_gestion_es_solo_del_administrador(request, cliente, quien):
    usuario = request.getfixturevalue(quien)

    for operacion in (
        lambda: listar_clientes(usuario),
        lambda: crear_cliente(usuario, {"nombre": "X"}),
        lambda: modificar_cliente(usuario, cliente, {"nombre": "X"}),
        lambda: dar_de_baja(usuario, cliente),
        lambda: reactivar(usuario, cliente),
    ):
        with pytest.raises(PermissionDenied):
            operacion()
    cliente.refresh_from_db()
    assert cliente.nombre == "Cliente de prueba" and cliente.activo


# Pantallas de CU-12


def test_cp114_el_administrador_gestiona_desde_la_pantalla(client, admin):
    client.force_login(admin)

    datos = {"nombre": "Juan Pérez", "telefono": "4444", "limite_credito": "50000"}
    assert client.post(NUEVO, datos).url == LISTADO
    cliente = Cliente.objects.get()
    assert cliente.limite_credito == Decimal("50000")
    assert "Juan Pérez" in client.get(LISTADO).content.decode()

    client.post(
        _editar(cliente),
        {"nombre": "Juan Pérez", "direccion": "San Martín 1", "observaciones": "Fin de mes"},
    )
    cliente.refresh_from_db()
    assert (cliente.direccion, cliente.observaciones) == ("San Martín 1", "Fin de mes")
    assert cliente.limite_credito is None

    assert "¿Dar de baja" in client.get(_baja(cliente)).content.decode()
    client.post(_baja(cliente))
    cliente.refresh_from_db()
    assert not cliente.activo
    assert _editar(cliente) not in client.get(LISTADO).content.decode()

    inactivos = client.get(LISTADO, {"inactivos": "1"}).content.decode()
    assert "Dado de baja" in inactivos and _reactivar(cliente) in inactivos
    client.post(_reactivar(cliente))
    cliente.refresh_from_db()
    assert cliente.activo


def test_los_errores_se_ven_junto_al_campo(client, admin):
    client.force_login(admin)

    respuesta = client.post(NUEVO, {"nombre": "", "limite_credito": "-5"})

    errores = respuesta.context["form"].errors
    assert "nombre" in errores and "limite_credito" in errores
    assert not Cliente.objects.exists()


def test_s1_la_baja_avisa_el_saldo_y_no_lo_borra(client, admin, cliente):
    _deuda(cliente, "1500")
    client.force_login(admin)

    assert "Debe" in client.get(_baja(cliente)).content.decode()
    client.post(_baja(cliente))

    assert MovimientoCuentaCorriente.objects.filter(cliente=cliente).count() == 1


def test_s1_sin_saldo_la_baja_no_avisa_deuda(client, admin, cliente):
    client.force_login(admin)

    assert "Debe" not in client.get(_baja(cliente)).content.decode()


def test_un_dado_de_baja_no_se_edita_y_reactivar_es_solo_por_post(client, admin, cliente):
    client.force_login(admin)
    assert client.get(_reactivar(cliente)).status_code == 405
    assert client.post(_reactivar(cliente)).status_code == 404  # está activo

    dar_de_baja(admin, cliente)

    assert client.get(_editar(cliente)).status_code == 404
    assert client.get(_baja(cliente)).status_code == 404


@pytest.mark.parametrize("quien", ["cajera_alta", "cajera", "duenio"])
def test_cp114_la_cajera_y_los_duenios_reciben_403(client, request, cliente, quien):
    client.force_login(request.getfixturevalue(quien))

    for url in (LISTADO, NUEVO, _editar(cliente), _baja(cliente)):
        assert client.get(url).status_code == 403, url
    assert client.post(NUEVO, {"nombre": "X"}).status_code == 403
    assert client.post(_baja(cliente)).status_code == 403
    assert client.post(_reactivar(cliente)).status_code == 403
    assert LISTADO not in client.get(reverse("inicio")).content.decode()
    assert Cliente.objects.count() == 1


def test_s2_el_menu_del_administrador_enlaza_clientes(client, admin):
    client.force_login(admin)

    assert f'href="{LISTADO}"' in client.get(reverse("inicio")).content.decode()


def test_sin_sesion_redirige_al_ingreso(client):
    assert client.get(LISTADO).url.startswith(reverse("usuarios:ingresar"))


# Listado: saldo, límite y deuda vencida (S-7, DEC-115, DEC-109)


def test_s7_el_listado_muestra_saldo_limite_y_deuda_vencida(client, admin):
    sin_limite = Cliente.objects.create(nombre="Ana Sin Límite")
    sin_credito = Cliente.objects.create(nombre="Beto Sin Crédito", limite_credito=0)
    con_limite = Cliente.objects.create(nombre="Carla Con Límite", limite_credito=50000)
    _deuda(con_limite, "1200", dias_atras=45)
    client.force_login(admin)

    respuesta = client.get(LISTADO)
    html = respuesta.content.decode()

    filas = {c.nombre: c for c in respuesta.context["pagina"]}
    assert filas[sin_limite.nombre].texto_limite == "Sin límite"
    assert filas[sin_credito.nombre].texto_limite == "Sin crédito habilitado"
    assert filas[con_limite.nombre].saldo == Decimal("1200.00")
    assert filas[con_limite.nombre].deuda_vencida == Decimal("1200.00")
    assert "Sin límite" in html and "Sin crédito habilitado" in html
    assert "$ 50.000,00" in html and "Vencida $ 1.200,00" in html


def test_s7_filtro_solo_con_deuda_vencida_en_la_pantalla(client, admin, cliente):
    vencido = Cliente.objects.create(nombre="Con deuda vieja")
    _deuda(vencido, "1000", dias_atras=45)
    client.force_login(admin)

    respuesta = client.get(LISTADO, {"vencidos": "1"})

    assert [c.nombre for c in respuesta.context["pagina"]] == [vencido.nombre]


def test_dec118_pagina_de_a_25_y_conserva_los_filtros(client, admin):
    Cliente.objects.bulk_create(Cliente(nombre=f"Cliente {i:02}") for i in range(30))
    client.force_login(admin)

    primera = client.get(LISTADO, {"q": "cliente"})
    segunda = client.get(LISTADO, {"q": "cliente", "pagina": 2})

    assert len(primera.context["pagina"]) == 25
    assert len(segunda.context["pagina"]) == 5
    assert "q=cliente" in primera.content.decode() and "pagina=2" in primera.content.decode()


def test_r7_el_listado_no_hace_una_consulta_por_cliente(
    client, admin, django_assert_max_num_queries
):
    clientes = Cliente.objects.bulk_create(Cliente(nombre=f"Cliente {i:02}") for i in range(20))
    for cliente in clientes:
        _deuda(cliente, "100", dias_atras=40)
    client.force_login(admin)

    with django_assert_max_num_queries(12):
        client.get(LISTADO)


# SC-01 Elegir cliente (DEC-116, DEC-118)


def test_sc01_trae_activos_por_nombre_o_telefono_con_su_cuenta(admin):
    juan = Cliente.objects.create(nombre="Juan Pérez", telefono="381 555-0101", limite_credito=1000)
    Cliente.objects.create(nombre="Juan Dado de Baja", activo=False)
    _deuda(juan, "800", dias_atras=40)

    resultados, hay_mas = buscar_para_elegir(admin, "juan")

    assert not hay_mas
    assert resultados == [
        {
            "id": juan.pk,
            "nombre": "Juan Pérez",
            "telefono": "381 555-0101",
            "activo": True,
            "saldo": "800.00",
            "limite": "$ 1.000,00",
            "disponible": "200.00",
            "deuda_vencida": "800.00",
        }
    ]
    assert [r["id"] for r in buscar_para_elegir(admin, "0101")[0]] == [juan.pk]


def test_sc01_en_el_cobro_aparecen_los_dados_de_baja_que_deben(admin):
    debe = Cliente.objects.create(nombre="Baja con deuda", activo=False)
    Cliente.objects.create(nombre="Baja sin deuda", activo=False)
    _deuda(debe, "500")

    assert buscar_para_elegir(admin, "baja")[0] == []
    assert [r["nombre"] for r in buscar_para_elegir(admin, "baja", para_cobro=True)[0]] == [
        "Baja con deuda"
    ]


def test_sc01_trae_hasta_el_tope_y_avisa_si_hay_mas(admin):
    Cliente.objects.bulk_create(
        Cliente(nombre=f"Cliente {i:03}") for i in range(LIMITE_BUSQUEDA + 1)
    )

    resultados, hay_mas = buscar_para_elegir(admin, "cliente")

    assert len(resultados) == LIMITE_BUSQUEDA and hay_mas


@pytest.mark.parametrize("quien", ["admin", "cajera", "cajera_alta"])
def test_sc01_el_administrador_y_la_cajera_eligen_clientes(client, request, cliente, quien):
    client.force_login(request.getfixturevalue(quien))

    respuesta = client.get(BUSCAR, {"q": "prueba"})

    assert respuesta.status_code == 200
    assert [r["id"] for r in respuesta.json()["resultados"]] == [cliente.pk]


def test_sc01_para_cobro_por_la_pantalla(client, admin):
    debe = Cliente.objects.create(nombre="Baja con deuda", activo=False)
    _deuda(debe, "500")
    client.force_login(admin)

    respuesta = client.get(BUSCAR, {"q": "baja", "para": "cobro"})

    assert [r["id"] for r in respuesta.json()["resultados"]] == [debe.pk]


def test_sc01_los_duenios_no_eligen_clientes(client, duenio, cliente):
    client.force_login(duenio)

    assert client.get(BUSCAR, {"q": "prueba"}).status_code == 403
    with pytest.raises(PermissionDenied):
        buscar_para_elegir(duenio, "prueba")


def test_sc01_solo_por_get(client, admin):
    client.force_login(admin)

    assert client.post(BUSCAR, {"q": "x"}).status_code == 405
