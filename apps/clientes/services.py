"""Clientes y cuenta corriente (H4): CU-12, SC-01, saldo, disponible, deuda vencida y saldo
inicial.

R-3 (DEC-131): este módulo concentra las reglas de la cuenta corriente; la venta (SC-03) y el
cobro (CU-04) las usan desde acá. El saldo no se guarda: sale de los movimientos (DEC-21).
R-4: `clientes` puede usar `caja`, pero nunca importa `ventas`, y `caja` nunca importa
`clientes`.
"""

import datetime
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.clientes.models import (
    TIPOS_QUE_SUMAN,
    Cliente,
    MovimientoCuentaCorriente,
    TipoMovimientoCuentaCorriente,
)
from apps.comun.models import pesos
from apps.usuarios.models import Rol

Tipo = TipoMovimientoCuentaCorriente

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")
# campo_monto: 12 dígitos con 2 decimales.
MONTO_FUERA_DE_RANGO = Decimal("10000000000")
MOTIVO_MAXIMO = 255


def puede_gestionar(usuario):
    """Solo el Administrador gestiona clientes y su saldo inicial (DEC-116, DEC-119)."""
    return usuario.is_authenticated and usuario.rol == Rol.ADMINISTRADOR


def _exigir_administrador(usuario, accion):
    if not puede_gestionar(usuario):
        raise PermissionDenied(f"Solo el administrador {accion}.")


def puede_elegir(usuario):
    """SC-01: el Administrador y la cajera eligen un cliente en la venta y el cobro (DEC-116)."""
    return usuario.is_authenticated and usuario.rol in (Rol.ADMINISTRADOR, Rol.CAJERA)


# Saldo y disponible (DEC-21, DEC-108, DEC-111, DEC-115)


def saldos_de_clientes(clientes):
    """Saldo de cada cliente, en una sola consulta para toda la lista (R-7).

    Saldo inicial, ventas a cuenta corriente y anulaciones de cobros suman; cobros y
    anulaciones de ventas y de saldos iniciales restan. Nunca es menor a 0 (DEC-111): las
    operaciones que lo bajan lo validan antes de guardar.
    """
    ids = [c.pk for c in clientes]
    filas = (
        MovimientoCuentaCorriente.objects.filter(cliente_id__in=ids)
        .values("cliente_id")
        .annotate(
            suma=Sum("monto", filter=Q(tipo__in=TIPOS_QUE_SUMAN)),
            resta=Sum("monto", filter=~Q(tipo__in=TIPOS_QUE_SUMAN)),
        )
    )
    saldos = {i: CERO for i in ids}
    for fila in filas:
        saldos[fila["cliente_id"]] = ((fila["suma"] or 0) - (fila["resta"] or 0)).quantize(CENTAVO)
    return saldos


def saldo(cliente):
    return saldos_de_clientes([cliente])[cliente.pk]


def disponible(cliente, saldo_actual=None):
    """Límite menos saldo; None si el cliente no tiene límite (DEC-108)."""
    if cliente.limite_credito is None:
        return None
    if saldo_actual is None:
        saldo_actual = saldo(cliente)
    return cliente.limite_credito - saldo_actual


def texto_limite(cliente):
    """Vacío y 0 significan cosas opuestas: "$ 0,00" se leería como sin límite (DEC-115)."""
    if cliente.limite_credito is None:
        return "Sin límite"
    if cliente.limite_credito == 0:
        return "Sin crédito habilitado"
    return pesos(cliente.limite_credito)


def validar_limite(cliente, monto):
    """Rechaza un cargo que deja el saldo por encima del límite de crédito (DEC-108, RI-05).

    Llegar justo al límite se permite. Sin límite, no hay tope.
    """
    if cliente.limite_credito is None:
        return
    if cliente.limite_credito == 0:
        raise ValidationError(
            f"{cliente} no tiene crédito habilitado (DEC-115).", code="sin_credito"
        )
    saldo_actual = saldo(cliente)
    libre = disponible(cliente, saldo_actual)
    if monto > libre:
        raise ValidationError(
            f"La venta supera el límite de crédito de {cliente}: saldo {pesos(saldo_actual)}, "
            f"disponible {pesos(max(libre, CERO))}.",
            code="limite_superado",
        )


def validar_saldo_suficiente(cliente, monto, que):
    """Un abono o una anulación no pueden dejar el saldo por debajo de 0 (DEC-111, DEC-114).

    `que` completa el mensaje: "el cobro", "la venta", "el saldo inicial".
    """
    saldo_actual = saldo(cliente)
    if monto > saldo_actual:
        raise ValidationError(
            f"El saldo actual de {cliente} es {pesos(saldo_actual)}, menor al monto de {que} "
            f"({pesos(monto)}).",
            code="saldo_insuficiente",
        )


# Deuda vencida (DEC-109): los cobros se imputan a los cargos más antiguos; lo que queda sin
# cubrir de los cargos con más días que el plazo es deuda vencida. Se calcula al consultar.


def _fecha_del_cargo(movimiento):
    """El saldo inicial vence por su fecha de origen (DEC-119); la venta, por su fecha."""
    if movimiento.tipo == Tipo.SALDO_INICIAL:
        return movimiento.fecha_origen
    return timezone.localdate(movimiento.fecha_hora)


def _deuda_vencida(movimientos, limite):
    anuladas = {m.venta_id for m in movimientos if m.tipo == Tipo.ANULACION_VENTA}
    cobros_anulados = {m.pago_cliente_id for m in movimientos if m.tipo == Tipo.ANULACION_PAGO}
    saldos_anulados = {
        m.saldo_inicial_id for m in movimientos if m.tipo == Tipo.ANULACION_SALDO_INICIAL
    }
    cargos = sorted(
        (
            m
            for m in movimientos
            if (m.tipo == Tipo.VENTA_FIADA and m.venta_id not in anuladas)
            or (m.tipo == Tipo.SALDO_INICIAL and m.pk not in saldos_anulados)
        ),
        key=lambda m: (_fecha_del_cargo(m), m.pk),
    )
    por_imputar = sum(
        (
            m.monto
            for m in movimientos
            if m.tipo == Tipo.PAGO and m.pago_cliente_id not in cobros_anulados
        ),
        CERO,
    )
    vencida = CERO
    for cargo in cargos:
        cubierto = min(por_imputar, cargo.monto)
        por_imputar -= cubierto
        if _fecha_del_cargo(cargo) < limite:
            vencida += cargo.monto - cubierto
    return vencida


def deudas_vencidas_de_clientes(clientes, hoy=None):
    """Deuda vencida de cada cliente, con una sola consulta para toda la lista (R-7)."""
    hoy = hoy or timezone.localdate()
    limite = hoy - datetime.timedelta(days=settings.PLAZO_VENCIMIENTO_CUENTA_CORRIENTE_DIAS)
    ids = [c.pk for c in clientes]
    por_cliente = defaultdict(list)
    for movimiento in MovimientoCuentaCorriente.objects.filter(cliente_id__in=ids).only(
        "cliente_id",
        "tipo",
        "monto",
        "fecha_hora",
        "fecha_origen",
        "venta_id",
        "pago_cliente_id",
        "saldo_inicial_id",
    ):
        por_cliente[movimiento.cliente_id].append(movimiento)
    return {i: _deuda_vencida(por_cliente[i], limite) for i in ids}


def deuda_vencida(cliente, hoy=None):
    return deudas_vencidas_de_clientes([cliente], hoy)[cliente.pk]


# Saldo inicial (DEC-119, RI-18)


def _validar_monto(monto):
    if monto is None or monto <= 0:
        raise ValidationError({"monto": "El monto tiene que ser mayor a 0."})
    if monto >= MONTO_FUERA_DE_RANGO:
        raise ValidationError({"monto": "El monto es demasiado grande."})
    if monto != monto.quantize(CENTAVO):
        raise ValidationError({"monto": "El monto admite hasta 2 decimales."})


def _validar_motivo(motivo, que):
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": f"Escribí el motivo {que}."})
    if len(motivo) > MOTIVO_MAXIMO:
        raise ValidationError({"motivo": f"El motivo admite hasta {MOTIVO_MAXIMO} caracteres."})
    return motivo


def saldo_inicial_vigente(cliente):
    """El saldo inicial sin anular del cliente, o None (RI-18)."""
    return (
        MovimientoCuentaCorriente.objects.filter(
            cliente=cliente, tipo=Tipo.SALDO_INICIAL, anulaciones__isnull=True
        )
        .order_by("pk")
        .first()
    )


def cargar_saldo_inicial(usuario, cliente, monto, fecha_origen, motivo):
    """Carga la deuda que el cliente ya tenía al empezar a usar el sistema (DEC-119).

    Solo el Administrador; uno vigente por cliente (RI-18). No pasa por la caja ni se valida
    contra el límite de crédito. Bloquea al cliente para que dos cargas no se crucen (S-9).
    """
    _exigir_administrador(usuario, "carga el saldo inicial")
    _validar_monto(monto)
    if fecha_origen is None:
        raise ValidationError({"fecha_origen": "Indicá la fecha de origen de la deuda."})
    if fecha_origen > timezone.localdate():
        raise ValidationError({"fecha_origen": "La fecha de origen no puede ser posterior a hoy."})
    motivo = _validar_motivo(motivo, "del saldo inicial")
    with transaction.atomic():
        cliente = Cliente.objects.select_for_update().get(pk=cliente.pk)
        if saldo_inicial_vigente(cliente) is not None:
            raise ValidationError(
                f"{cliente} ya tiene un saldo inicial: para cambiarlo, primero hay que anularlo.",
                code="saldo_inicial_repetido",
            )
        return MovimientoCuentaCorriente.objects.create(
            cliente=cliente,
            tipo=Tipo.SALDO_INICIAL,
            monto=monto,
            fecha_origen=fecha_origen,
            motivo=motivo,
        )


def anular_saldo_inicial(usuario, saldo_inicial, motivo):
    """Anula un saldo inicial con un movimiento inverso por el mismo monto (DEC-119).

    Se rechaza si el saldo actual del cliente es menor al monto (como DEC-114). Después se
    puede cargar otro. El saldo inicial no se toca.
    """
    _exigir_administrador(usuario, "anula el saldo inicial")
    motivo = _validar_motivo(motivo, "de la anulación")
    with transaction.atomic():
        cliente = Cliente.objects.select_for_update().get(pk=saldo_inicial.cliente_id)
        saldo_inicial = MovimientoCuentaCorriente.objects.get(pk=saldo_inicial.pk)
        if saldo_inicial.tipo != Tipo.SALDO_INICIAL:
            raise ValidationError("Ese movimiento no es un saldo inicial.")
        if saldo_inicial.anulaciones.exists():
            raise ValidationError("El saldo inicial ya está anulado.")
        validar_saldo_suficiente(cliente, saldo_inicial.monto, "el saldo inicial")
        return MovimientoCuentaCorriente.objects.create(
            # RI-15: el mismo cliente que el saldo inicial que anula.
            cliente=cliente,
            tipo=Tipo.ANULACION_SALDO_INICIAL,
            monto=saldo_inicial.monto,
            saldo_inicial=saldo_inicial,
            motivo=motivo,
        )


# CU-12 Gestionar clientes (DEC-116 a DEC-118; S-1, S-7). Mismo patrón que CU-13.

CAMPOS_EDITABLES = ["nombre", "telefono", "direccion", "limite_credito", "observaciones"]
# Tope de la lista de SC-01, como el buscador de la venta (DEC-97).
LIMITE_BUSQUEDA = 50


def _por_texto(clientes, texto):
    """Por nombre o teléfono, sin distinguir mayúsculas (DEC-118)."""
    texto = (texto or "").strip()
    if texto:
        clientes = clientes.filter(Q(nombre__icontains=texto) | Q(telefono__icontains=texto))
    return clientes


def listar_clientes(usuario, texto="", incluir_inactivos=False, solo_vencidos=False, hoy=None):
    """Ordenados por nombre; los dados de baja solo si se piden. "Solo con deuda vencida"
    calcula la deuda de los que coinciden con una sola consulta (S-7, R-7)."""
    _exigir_administrador(usuario, "gestiona clientes")
    clientes = Cliente.objects.order_by("nombre", "pk")
    if not incluir_inactivos:
        clientes = clientes.filter(activo=True)
    clientes = _por_texto(clientes, texto)
    if solo_vencidos:
        vencidas = deudas_vencidas_de_clientes(list(clientes), hoy)
        clientes = clientes.filter(pk__in=[pk for pk, monto in vencidas.items() if monto > 0])
    return clientes


def con_cuenta(clientes, hoy=None):
    """Agrega a cada cliente saldo, deuda vencida y el texto del límite (DEC-115), con una
    consulta para los saldos y otra para la deuda vencida de toda la lista (R-7)."""
    clientes = list(clientes)
    saldos = saldos_de_clientes(clientes)
    vencidas = deudas_vencidas_de_clientes(clientes, hoy)
    for cliente in clientes:
        cliente.saldo = saldos[cliente.pk]
        cliente.deuda_vencida = vencidas[cliente.pk]
        cliente.texto_limite = texto_limite(cliente)
        cliente.disponible = disponible(cliente, cliente.saldo)
    return clientes


def cliente_editable(pk):
    """Cliente activo; uno dado de baja primero se reactiva. Cliente.DoesNotExist si no."""
    return Cliente.objects.get(pk=pk, activo=True)


def cliente_dado_de_baja(pk):
    """Cliente inactivo, para reactivarlo. Cliente.DoesNotExist si no lo es."""
    return Cliente.objects.get(pk=pk, activo=False)


def _guardar(cliente, datos):
    for campo in CAMPOS_EDITABLES:
        valor = datos.get(campo)
        if campo == "limite_credito":
            # Vacío = sin límite; 0 = sin crédito habilitado (DEC-108, DEC-115).
            cliente.limite_credito = valor
        else:
            setattr(cliente, campo, (valor or "").strip())
    cliente.full_clean()
    cliente.save()
    return cliente


def crear_cliente(usuario, datos):
    _exigir_administrador(usuario, "da de alta clientes")
    return _guardar(Cliente(), datos)


def modificar_cliente(usuario, cliente, datos):
    _exigir_administrador(usuario, "modifica clientes")
    return _guardar(cliente, datos)


def dar_de_baja(usuario, cliente):
    """Baja lógica: sus movimientos no cambian (RI-11) y la deuda sigue, con su saldo para
    cobrar (DEC-116, S-1). Un cliente dado de baja no compra a cuenta corriente."""
    _exigir_administrador(usuario, "da de baja clientes")
    cliente.activo = False
    cliente.save(update_fields=["activo", "actualizado_en"])
    return cliente


def reactivar(usuario, cliente):
    """Vuelve a activar un cliente dado de baja (S-1, como DEC-85 y DEC-87)."""
    _exigir_administrador(usuario, "reactiva clientes")
    cliente.activo = True
    cliente.save(update_fields=["activo", "actualizado_en"])
    return cliente


# SC-01 Elegir cliente (DEC-116, DEC-118): lo usan la venta (SC-03) y el cobro (CU-04).


def _para_elegir(cliente):
    return {
        "id": cliente.pk,
        "nombre": cliente.nombre,
        "telefono": cliente.telefono,
        "activo": cliente.activo,
        "saldo": str(cliente.saldo),
        "limite": cliente.texto_limite,
        "disponible": None if cliente.disponible is None else str(cliente.disponible),
        "deuda_vencida": str(cliente.deuda_vencida),
    }


def buscar_para_elegir(usuario, texto, para_cobro=False, hoy=None):
    """Clientes activos por nombre o teléfono, con saldo, límite, disponible y deuda vencida.

    En el cobro también aparecen los dados de baja que todavía deben (DEC-116). Devuelve hasta
    LIMITE_BUSQUEDA y si hay más, como el buscador de la venta (DEC-97).
    """
    if not puede_elegir(usuario):
        raise PermissionDenied("Solo el administrador y la cajera eligen clientes.")
    clientes = _por_texto(Cliente.objects.order_by("nombre", "pk"), texto)
    if para_cobro:
        con_deuda = [
            pk
            for pk, monto in saldos_de_clientes(list(clientes.filter(activo=False))).items()
            if monto > 0
        ]
        clientes = clientes.filter(Q(activo=True) | Q(pk__in=con_deuda))
    else:
        clientes = clientes.filter(activo=True)
    encontrados = list(clientes[: LIMITE_BUSQUEDA + 1])
    hay_mas = len(encontrados) > LIMITE_BUSQUEDA
    return [_para_elegir(c) for c in con_cuenta(encontrados[:LIMITE_BUSQUEDA], hoy)], hay_mas
