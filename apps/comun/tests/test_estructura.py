"""CP-72 y CP-73: la base que crean las migraciones coincide con 05-modelo-datos.md."""

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db

APPS_DEL_SISTEMA = ["usuarios", "caja", "ventas", "catalogo", "proveedores", "clientes"]

TABLAS = {
    "usuario",
    "medio_pago",
    "caja",
    "cierre_caja_detalle",
    "movimiento_caja",
    "venta",
    "detalle_venta",
    "categoria",
    "producto",
    "proveedor",
    "producto_proveedor",
    "ingreso_mercaderia",
    "detalle_ingreso",
    "pago_proveedor",
    "cliente",
    "pago_cliente",
    "movimiento_cuenta_corriente",
}

# Restricciones de 05 (7.4) y RI-16, por nombre.
CHECKS = {
    "usuario": ["usuario_rol_valido", "usuario_panel_solo_administrador"],
    "caja": [
        "caja_turno_valido",
        "caja_estado_valido",
        "caja_cerrada_en_solo_si_cerrada",
        "caja_monto_inicial_no_negativo",
    ],
    "cierre_caja_detalle": ["cierre_caja_detalle_contado_no_negativo"],
    "movimiento_caja": [
        "movimiento_caja_monto_positivo",
        "movimiento_caja_tipo_valido",
        "movimiento_caja_concepto_valido",
        "movimiento_caja_referencia_segun_concepto",
    ],
    "venta": ["venta_monto_total_no_negativo"],
    "detalle_venta": [
        "detalle_venta_cantidad_positiva",
        "detalle_venta_precio_no_negativo",
        "detalle_venta_subtotal_no_negativo",
    ],
    "producto": [
        "producto_plus_interno_no_vacio",
        "producto_precio_venta_no_negativo",
        "producto_stock_minimo_no_negativo",
        "producto_unidad_medida_valida",
    ],
    "producto_proveedor": ["producto_proveedor_precio_no_negativo"],
    "ingreso_mercaderia": [
        "ingreso_mercaderia_total_no_negativo",
        "ingreso_mercaderia_condicion_pago_valida",
    ],
    "detalle_ingreso": ["detalle_ingreso_cantidad_positiva", "detalle_ingreso_precio_no_negativo"],
    "pago_proveedor": ["pago_proveedor_monto_positivo"],
    "cliente": ["cliente_limite_credito_no_negativo"],
    "pago_cliente": ["pago_cliente_monto_positivo"],
    "movimiento_cuenta_corriente": [
        "movimiento_cuenta_corriente_monto_positivo",
        "movimiento_cuenta_corriente_tipo_valido",
        "movimiento_cuenta_corriente_referencia_segun_tipo",
    ],
}

# (tabla, nombre, columnas, parcial)
UNICOS = [
    ("caja", "caja_unica_por_fecha_turno", ["fecha", "turno"], False),
    ("caja", "caja_una_sola_abierta", ["estado"], True),
    (
        "cierre_caja_detalle",
        "cierre_caja_detalle_caja_medio_unico",
        ["caja_id", "medio_pago_id"],
        False,
    ),
    ("producto", "producto_plus_interno_unico", ["plus_interno"], True),
    ("producto_proveedor", "producto_proveedor_unico", ["producto_id", "proveedor_id"], False),
    ("movimiento_cuenta_corriente", "movimiento_cuenta_corriente_venta_unica", ["venta_id"], True),
]

# Índices de 05 (7.5) que no salen de una clave única: (tabla, columnas, parcial).
INDICES = [
    ("venta", ["caja_id", "fecha_hora"], False),
    ("venta", ["cliente_id"], False),
    ("detalle_venta", ["producto_id"], False),
    ("movimiento_caja", ["caja_id", "medio_pago_id"], False),
    ("movimiento_cuenta_corriente", ["cliente_id", "fecha_hora"], False),
    ("pago_proveedor", ["proveedor_id"], False),
    ("pago_proveedor", ["ingreso_id"], False),
    ("producto", ["nombre"], False),
    ("detalle_ingreso", ["fecha_vencimiento"], True),
]


def _restricciones(tabla):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, tabla)


def _definicion_indice(nombre):
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s", [nombre])
        fila = cursor.fetchone()
    return fila[0] if fila else ""


def _modelos():
    return [m for app in APPS_DEL_SISTEMA for m in apps.get_app_config(app).get_models()]


# CP-72


def test_cp72_no_quedan_migraciones_sin_aplicar():
    executor = MigrationExecutor(connection)
    objetivos = executor.loader.graph.leaf_nodes()

    assert executor.migration_plan(objetivos) == []


def test_cp72_los_modelos_no_tienen_cambios_sin_migrar():
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


# CP-73


def test_cp73_existen_las_17_tablas_y_ninguna_condicional():
    tablas = set(connection.introspection.table_names())

    assert TABLAS <= tablas
    assert {m._meta.db_table for m in _modelos()} == TABLAS
    assert not {"pedido_proveedor", "faltante_stock", "movimiento_stock"} & tablas


@pytest.mark.parametrize("tabla", sorted(TABLAS))
def test_cp73_toda_tabla_tiene_auditoria(tabla):
    with connection.cursor() as cursor:
        columnas = {c.name for c in connection.introspection.get_table_description(cursor, tabla)}

    assert {"id", "creado_en", "actualizado_en"} <= columnas


@pytest.mark.parametrize(("tabla", "nombre"), [(t, n) for t, ns in CHECKS.items() for n in ns])
def test_cp73_existe_cada_check(tabla, nombre):
    restriccion = _restricciones(tabla).get(nombre)

    assert restriccion is not None, nombre
    assert restriccion["check"]


@pytest.mark.parametrize(("tabla", "nombre", "columnas", "parcial"), UNICOS)
def test_cp73_existe_cada_unico(tabla, nombre, columnas, parcial):
    restriccion = _restricciones(tabla).get(nombre)

    assert restriccion is not None, nombre
    assert restriccion["unique"]
    assert restriccion["columns"] == columnas
    assert (" WHERE " in _definicion_indice(nombre)) == parcial


@pytest.mark.parametrize(
    ("tabla", "nombre"),
    [("medio_pago", "medio_pago_nombre_unico"), ("categoria", "categoria_nombre_unico")],
)
def test_cp73_nombre_unico_sin_distinguir_mayusculas(tabla, nombre):
    restriccion = _restricciones(tabla).get(nombre)

    assert restriccion is not None, nombre
    assert restriccion["unique"]
    assert "lower((nombre)" in _definicion_indice(nombre).lower()


def test_cp73_nombre_de_usuario_unico():
    assert any(
        r["unique"] and r["columns"] == ["username"] for r in _restricciones("usuario").values()
    )


@pytest.mark.parametrize(("tabla", "columnas", "parcial"), INDICES)
def test_cp73_existe_cada_indice(tabla, columnas, parcial):
    indices = {
        nombre: r
        for nombre, r in _restricciones(tabla).items()
        if r["index"] and r["columns"] == columnas
    }

    assert indices, f"{tabla}{columnas}"
    assert any((" WHERE " in _definicion_indice(n)) == parcial for n in indices)


@pytest.mark.parametrize("modelo", _modelos(), ids=lambda m: m._meta.db_table)
def test_cp73_toda_clave_foranea_existe_en_la_base_y_protege_el_borrado(modelo):
    claves = [f for f in modelo._meta.get_fields() if isinstance(f, models.ForeignKey)]
    restricciones = _restricciones(modelo._meta.db_table).values()

    for campo in claves:
        assert campo.remote_field.on_delete is models.PROTECT, campo.name
        assert any(r["foreign_key"] and r["columns"] == [campo.column] for r in restricciones), (
            campo.column
        )
