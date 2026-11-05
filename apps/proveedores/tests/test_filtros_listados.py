"""CP-133: filtros por fecha y proveedor en los listados de ingresos y pagos (DEC-139, DEC-152)."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.proveedores.models import CondicionPago, IngresoMercaderia, PagoProveedor, Proveedor

pytestmark = pytest.mark.django_db

D10 = datetime.date(2026, 1, 10)
D15 = datetime.date(2026, 1, 15)
D20 = datetime.date(2026, 1, 20)


@pytest.fixture
def datos(admin, efectivo):
    activo = Proveedor.objects.create(nombre="Frigorífico Sur")
    de_baja = Proveedor.objects.create(nombre="Distribuidora Norte", activo=False)

    def ingreso(proveedor, fecha):
        return IngresoMercaderia.objects.create(
            fecha=fecha,
            proveedor=proveedor,
            usuario=admin,
            total=Decimal("1000"),
            condicion_pago=CondicionPago.A_CREDITO,
        )

    def pago(proveedor, fecha):
        return PagoProveedor.objects.create(
            proveedor=proveedor,
            monto=Decimal("100"),
            medio_pago=efectivo,
            usuario=admin,
            fecha_hora=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(10))),
        )

    return {
        "activo": activo,
        "de_baja": de_baja,
        "ingresos": [ingreso(activo, D10), ingreso(de_baja, D15), ingreso(activo, D20)],
        "pagos": [pago(activo, D10), pago(de_baja, D15), pago(activo, D20)],
    }


def _lista(client, url, **filtros):
    respuesta = client.get(reverse(url), filtros)
    assert respuesta.status_code == 200
    return list(respuesta.context["pagina"].object_list), respuesta


@pytest.mark.parametrize(
    ("url", "clave"), [("proveedores:ingresos", "ingresos"), ("proveedores:pagos", "pagos")]
)
def test_cp133_sin_filtro_lista_todo_y_filtra_por_fechas(client, admin, datos, url, clave):
    viejo, medio, nuevo = datos[clave]
    client.force_login(admin)

    assert _lista(client, url)[0] == [nuevo, medio, viejo]
    assert _lista(client, url, desde=D15)[0] == [nuevo, medio]
    assert _lista(client, url, hasta=D15)[0] == [medio, viejo]
    assert _lista(client, url, desde=D15, hasta=D15)[0] == [medio]


@pytest.mark.parametrize(
    ("url", "clave"), [("proveedores:ingresos", "ingresos"), ("proveedores:pagos", "pagos")]
)
def test_cp133_filtra_por_proveedor_tambien_dado_de_baja_y_combina(
    client, admin, datos, url, clave
):
    viejo, medio, nuevo = datos[clave]
    client.force_login(admin)

    assert _lista(client, url, proveedor=datos["de_baja"].pk)[0] == [medio]
    assert _lista(client, url, proveedor=datos["activo"].pk, desde=D15)[0] == [nuevo]
    opciones = _lista(client, url)[1].content.decode()
    assert "Distribuidora Norte (dado de baja)" in opciones


@pytest.mark.parametrize("url", ["proveedores:ingresos", "proveedores:pagos"])
@pytest.mark.parametrize(
    ("filtro", "campo"),
    [
        ({"desde": "2026-01-20", "hasta": "2026-01-10"}, "desde"),
        ({"hasta": "2999-01-01"}, "hasta"),
    ],
)
def test_cp133_un_rango_invalido_muestra_el_error_y_no_lista(
    client, admin, datos, url, filtro, campo
):
    client.force_login(admin)

    lista, respuesta = _lista(client, url, **filtro)

    assert respuesta.context["form"].errors[campo]
    assert lista == []
    assert "Corregí el filtro para ver el listado" in respuesta.content.decode()


@pytest.mark.parametrize(
    ("url", "clave"), [("proveedores:ingresos", "ingresos"), ("proveedores:pagos", "pagos")]
)
def test_cp133_los_filtros_se_conservan_al_paginar(client, admin, datos, url, clave):
    viejo = datos[clave][0]
    modelo = type(viejo)
    for _ in range(26):
        viejo.pk = None
        viejo.save()
    client.force_login(admin)

    lista, respuesta = _lista(client, url, proveedor=datos["activo"].pk, hasta=D10)

    assert len(lista) == 25 and modelo.objects.filter(proveedor=datos["activo"]).count() == 28
    assert (
        f"proveedor={datos['activo'].pk}&amp;hasta=2026-01-10&amp;pagina=2"
        in respuesta.content.decode()
    )
    segunda, _ = _lista(client, url, proveedor=datos["activo"].pk, hasta=D10, pagina=2)
    assert len(segunda) == 2


@pytest.mark.parametrize("url", ["proveedores:ingresos", "proveedores:pagos"])
def test_cp133_la_cajera_no_ve_los_listados(client, cajera, url):
    client.force_login(cajera)

    assert client.get(reverse(url), {"desde": "2026-01-01"}).status_code == 403
