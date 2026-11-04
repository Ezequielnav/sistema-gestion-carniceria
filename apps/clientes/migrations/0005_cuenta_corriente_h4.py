"""Etapa 1 de H4: se quitan ANTICIPO (DEC-111) y fecha_vencimiento (DEC-109), y condiciones
pasa a observaciones sin perder datos (DEC-117).

Si la base ya tiene anticipos o fechas de vencimiento cargadas, la migración se detiene antes
de tocar nada (SPEC-H4, sección 3): esos datos no tienen lugar en el modelo nuevo.
"""

from django.db import migrations


def verificar_sin_datos_que_se_pierden(apps, schema_editor):
    Movimiento = apps.get_model("clientes", "MovimientoCuentaCorriente")
    anticipos = Movimiento.objects.filter(tipo="ANTICIPO").count()
    con_vencimiento = Movimiento.objects.filter(fecha_vencimiento__isnull=False).count()
    if anticipos or con_vencimiento:
        raise RuntimeError(
            "La base tiene movimientos de cuenta corriente que el modelo de H4 ya no admite: "
            f"{anticipos} anticipos y {con_vencimiento} con fecha de vencimiento. "
            "Revisarlos antes de migrar (DEC-109, DEC-111)."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("clientes", "0004_alter_cliente_limite_credito_and_more"),
    ]

    operations = [
        migrations.RunPython(verificar_sin_datos_que_se_pierden, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="cliente",
            old_name="condiciones",
            new_name="observaciones",
        ),
    ]
