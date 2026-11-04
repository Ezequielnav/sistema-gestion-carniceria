"""Escenario fijo de los reportes de CU-09: dos cajas en la misma fecha y turno (DEC-83), una
venta a cuenta corriente, una venta anulada, cobros con caja y sin caja y un cobro anulado."""

import datetime
from decimal import Decimal

from django.utils import timezone

from apps.caja.models import Caja, CierreCajaDetalle, EstadoCaja, MedioPago, Turno
from apps.catalogo.models import Producto, UnidadMedida
from apps.clientes.models import Cliente, EstadoPagoCliente, PagoCliente
from apps.usuarios.models import Rol, Usuario
from apps.ventas.models import DetalleVenta, EstadoVenta, Venta

D15 = datetime.date(2026, 1, 15)
D16 = datetime.date(2026, 1, 16)


def usuario(username, rol):
    return Usuario.objects.create_user(
        username=username, password="clave-de-prueba-123", nombre_completo=username, rol=rol
    )


def caja_cerrada(fecha, turno, cajera):
    return Caja.objects.create(
        fecha=fecha,
        turno=turno,
        usuario=cajera,
        estado=EstadoCaja.CERRADA,
        cerrada_en=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(14))),
        cerrada_por_usuario=cajera,
    )


def venta(caja, medio, monto, renglones=(), anulada=False, cliente=None):
    venta = Venta.objects.create(
        caja=caja,
        usuario=caja.usuario,
        medio_pago=medio,
        monto_total=Decimal(monto),
        cliente=cliente,
    )
    for producto, cantidad, subtotal in renglones:
        DetalleVenta.objects.create(
            venta=venta,
            producto=producto,
            cantidad=Decimal(cantidad),
            precio_unitario=Decimal(subtotal) / Decimal(cantidad),
            subtotal=Decimal(subtotal),
        )
    if anulada:
        Venta.objects.filter(pk=venta.pk).update(
            estado=EstadoVenta.ANULADA,
            anulada_en=timezone.now(),
            anulada_por_usuario=caja.usuario,
            motivo_anulacion="Error de carga",
        )
    return venta


def cobro(fecha, medio, monto, entra_a_caja, usuario, cliente, anulado=False):
    cobro = PagoCliente.objects.create(
        cliente=cliente,
        monto=Decimal(monto),
        medio_pago=medio,
        usuario=usuario,
        entra_a_caja=entra_a_caja,
        fecha_hora=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(11))),
    )
    if anulado:
        PagoCliente.objects.filter(pk=cobro.pk).update(
            estado=EstadoPagoCliente.ANULADO,
            anulado_en=timezone.now(),
            anulado_por_usuario=usuario,
            motivo_anulacion="Error de carga",
        )
    return cobro


def armar_escenario(admin):
    cajera = usuario("cajera", Rol.CAJERA)
    efectivo = MedioPago.objects.create(nombre="Efectivo", es_efectivo=True)
    tarjeta = MedioPago.objects.create(nombre="Tarjeta")
    cuenta = MedioPago.objects.create(nombre="Cuenta corriente", ingresa_a_caja=False)
    cliente = Cliente.objects.create(nombre="Cliente")
    asado = Producto.objects.create(
        nombre="Asado",
        precio_venta=Decimal("500"),
        unidad_medida=UnidadMedida.KG,
        controla_stock=False,
    )
    yerba = Producto.objects.create(
        nombre="Yerba",
        precio_venta=Decimal("100"),
        unidad_medida=UnidadMedida.UNIDAD,
        controla_stock=False,
    )
    # Dos cajas el 15 a la mañana (DEC-83), una a la tarde y una el 16.
    manana_1 = caja_cerrada(D15, Turno.MANANA, cajera)
    manana_2 = caja_cerrada(D15, Turno.MANANA, cajera)
    tarde = caja_cerrada(D15, Turno.TARDE, cajera)
    dia_16 = caja_cerrada(D16, Turno.MANANA, cajera)
    venta(manana_1, efectivo, "1000", [(asado, "2", "1000")])
    venta(manana_2, tarjeta, "500", [(yerba, "5", "500")])
    venta(tarde, cuenta, "300", [(yerba, "3", "300")], cliente=cliente)
    venta(tarde, efectivo, "200", [(asado, "0.4", "200")], anulada=True)
    venta(dia_16, efectivo, "700", [(asado, "1.4", "700")])
    cobro(D15, efectivo, "400", True, cajera, cliente)
    cobro(D15, tarjeta, "250", False, admin, cliente)
    cobro(D16, efectivo, "100", True, cajera, cliente, anulado=True)
    CierreCajaDetalle.objects.create(
        caja=manana_1,
        medio_pago=efectivo,
        monto_sistema=Decimal("1000"),
        monto_contado=Decimal("900"),
    )
    return {
        "manana_1": manana_1,
        "manana_2": manana_2,
        "tarde": tarde,
        "dia_16": dia_16,
        "cliente": cliente,
        "efectivo": efectivo,
    }
