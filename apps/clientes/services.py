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
from django.db.models import Case, DecimalField, F, Q, Sum, When, Window
from django.utils import timezone

from apps.caja.models import ConceptoMovimientoCaja, EstadoCaja, MedioPago
from apps.caja.services import (
    MENSAJE_SIN_CAJA_PARA_REVERSA,
    caja_abierta,
    caja_del_dia_bloqueada,
    caja_para_reversa_de_cobro,
    caja_que_recibe_la_reversa,
    es_de_otro_dia,
    ingreso_de_cobro,
    registrar_ingreso_cobro,
    registrar_reversa_cobro,
)
from apps.clientes.models import (
    TIPOS_QUE_SUMAN,
    Cliente,
    EstadoPagoCliente,
    MovimientoCuentaCorriente,
    PagoCliente,
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
    """El Administrador y la cajera eligen un cliente en la venta y el cobro (SC-01, DEC-116) y
    cobran (DEC-110)."""
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
        raise ValidationError(f"{cliente} no tiene crédito habilitado.", code="sin_credito")
    saldo_actual = saldo(cliente)
    libre = disponible(cliente, saldo_actual)
    if monto > libre:
        raise ValidationError(
            f"La venta supera el límite de crédito de {cliente}: saldo {pesos(saldo_actual)}, "
            f"disponible {pesos(max(libre, CERO))}.",
            code="limite_superado",
        )


def validar_saldo_suficiente(cliente, monto, de_que):
    """Un abono o una anulación no pueden dejar el saldo por debajo de 0 (DEC-111, DEC-114).

    `de_que` completa el mensaje: "del cobro", "de la venta", "del saldo inicial".
    """
    saldo_actual = saldo(cliente)
    if monto > saldo_actual:
        raise ValidationError(
            f"El saldo actual de {cliente} es {pesos(saldo_actual)}, menor al monto {de_que} "
            f"({pesos(monto)}).",
            code="saldo_insuficiente",
        )


# SC-03 Vender a cuenta corriente (DEC-108, DEC-113, DEC-114). La venta llama a estas
# funciones dentro de su transacción, después de bloquear la caja (DEC-128).


def bloquear_cliente(cliente_id):
    """El cliente con su fila bloqueada hasta terminar la operación (DEC-128). Así dos ventas,
    o una venta y un cobro, no validan límite y saldo con el mismo dato viejo."""
    return Cliente.objects.select_for_update().get(pk=cliente_id)


def registrar_cargo(venta):
    """La deuda de una venta a cuenta corriente: `VENTA_FIADA` por su total, sin caja (R-2).

    Se rechaza si el cliente está dado de baja (DEC-116) o si pasa su límite (DEC-108). El
    cliente tiene que venir bloqueado con `bloquear_cliente`.
    """
    cliente = venta.cliente
    if not cliente.activo:
        raise ValidationError(
            f"{cliente} está dado de baja: no compra a cuenta corriente.", code="cliente_inactivo"
        )
    validar_limite(cliente, venta.monto_total)
    return MovimientoCuentaCorriente.objects.create(
        cliente=cliente,
        fecha_hora=venta.fecha_hora,
        tipo=Tipo.VENTA_FIADA,
        monto=venta.monto_total,
        venta=venta,
    )


def registrar_anulacion_de_cargo(venta):
    """L1: anular una venta a cuenta corriente revierte su deuda con `ANULACION_VENTA`, en lugar
    del egreso de caja (DEC-113). Se rechaza si el saldo actual es menor al total (DEC-114)."""
    cliente = bloquear_cliente(venta.cliente_id)
    validar_saldo_suficiente(cliente, venta.monto_total, "de la venta")
    return MovimientoCuentaCorriente.objects.create(
        # RI-15: el mismo cliente que la venta.
        cliente=cliente,
        tipo=Tipo.ANULACION_VENTA,
        monto=venta.monto_total,
        venta=venta,
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
        cliente = bloquear_cliente(cliente.pk)
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
        cliente = bloquear_cliente(saldo_inicial.cliente_id)
        saldo_inicial = MovimientoCuentaCorriente.objects.get(pk=saldo_inicial.pk)
        if saldo_inicial.tipo != Tipo.SALDO_INICIAL:
            raise ValidationError("Ese movimiento no es un saldo inicial.")
        if saldo_inicial.anulaciones.exists():
            raise ValidationError("El saldo inicial ya está anulado.")
        validar_saldo_suficiente(cliente, saldo_inicial.monto, "del saldo inicial")
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


def listar_clientes(usuario, texto="", incluir_inactivos=False, solo_vencidos=False):
    """Ordenados por nombre; los dados de baja solo si se piden. "Solo con deuda vencida"
    calcula la deuda de los que coinciden con una sola consulta (S-7, R-7)."""
    _exigir_administrador(usuario, "gestiona clientes")
    clientes = Cliente.objects.order_by("nombre", "pk")
    if not incluir_inactivos:
        clientes = clientes.filter(activo=True)
    clientes = _por_texto(clientes, texto)
    if solo_vencidos:
        vencidas = deudas_vencidas_de_clientes(list(clientes))
        clientes = clientes.filter(pk__in=[pk for pk, monto in vencidas.items() if monto > 0])
    return clientes


def con_cuenta(clientes):
    """Agrega a cada cliente saldo, deuda vencida y el texto del límite (DEC-115), con una
    consulta para los saldos y otra para la deuda vencida de toda la lista (R-7)."""
    clientes = list(clientes)
    saldos = saldos_de_clientes(clientes)
    vencidas = deudas_vencidas_de_clientes(clientes)
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


def cliente_para_elegir(usuario, pk, para_cobro=False):
    """Un cliente con los datos de SC-01, para mostrarlo ya elegido (por ejemplo, al llegar al
    cobro desde el listado), o None si no se puede elegir."""
    if not puede_elegir(usuario):
        raise PermissionDenied("Solo el administrador y la cajera eligen clientes.")
    cliente = Cliente.objects.filter(pk=pk).first()
    if cliente is None:
        return None
    (cliente,) = con_cuenta([cliente])
    if not cliente.activo and not (para_cobro and cliente.saldo > 0):
        return None
    return _para_elegir(cliente)


def buscar_para_elegir(usuario, texto, para_cobro=False):
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
    return [_para_elegir(c) for c in con_cuenta(encontrados[:LIMITE_BUSQUEDA])], hay_mas


# CU-04 Registrar pago de cliente: el cobro y su anulación (DEC-110, DEC-111, DEC-113; S-6).


def medios_para_cobrar():
    """Medios activos que ingresan a caja: una deuda no se paga con cuenta corriente (DEC-110)."""
    return MedioPago.objects.filter(activo=True, ingresa_a_caja=True).order_by("pk")


def registrar_cobro(usuario, cliente, monto, medio, entra_a_caja=True):
    """Cobra parte o todo el saldo del cliente, nunca más (DEC-111).

    El cobro entra a la caja abierta de hoy con su medio (RN-04). La cajera siempre cobra en
    caja; el Administrador puede registrarlo sin movimiento de caja (DEC-110, criterio de
    DEC-106). Bloquea caja y después cliente (DEC-128). Se puede cobrar a un cliente dado de
    baja que todavía debe (DEC-116).
    """
    if not puede_elegir(usuario):
        raise PermissionDenied("Solo el administrador y la cajera cobran cuentas corrientes.")
    if not medios_para_cobrar().filter(pk=medio.pk).exists():
        raise ValidationError(
            {"medio_pago": "Ese medio de pago no se puede usar para cobrar."}, code="medio_pago"
        )
    _validar_monto(monto)
    if usuario.rol != Rol.ADMINISTRADOR:
        entra_a_caja = True
    with transaction.atomic():
        caja = caja_del_dia_bloqueada() if entra_a_caja else None
        cliente = bloquear_cliente(cliente.pk)
        saldo_actual = saldo(cliente)
        if saldo_actual <= 0:
            raise ValidationError(f"{cliente} no tiene saldo para cobrar.", code="sin_saldo")
        if monto > saldo_actual:
            raise ValidationError(
                {
                    "monto": f"El saldo de {cliente} es {pesos(saldo_actual)}: es el máximo a "
                    "cobrar."
                },
                code="supera_el_saldo",
            )
        pago = PagoCliente.objects.create(
            cliente=cliente,
            monto=monto,
            medio_pago=medio,
            usuario=usuario,
            entra_a_caja=entra_a_caja,
        )
        MovimientoCuentaCorriente.objects.create(
            cliente=cliente,
            fecha_hora=pago.fecha_hora,
            tipo=Tipo.PAGO,
            monto=monto,
            pago_cliente=pago,
        )
        if entra_a_caja:
            registrar_ingreso_cobro(pago, usuario, caja)
    return pago


def cobro_con_detalles(usuario, pk):
    """El cobro con lo que muestra su detalle; solo el Administrador (S-10, S-11)."""
    _exigir_administrador(usuario, "consulta los cobros")
    return PagoCliente.objects.select_related(
        "cliente", "medio_pago", "usuario", "anulado_por_usuario"
    ).get(pk=pk)


def caja_de_la_reversa(cobro):
    """La caja donde iría la reversa de un cobro que entró a caja: la de su ingreso si sigue
    abierta, si no la caja abierta (DEC-166, DEC-178), o None. Para mostrarla en el detalle."""
    return caja_que_recibe_la_reversa(ingreso_de_cobro(cobro).caja)


_SIN_CALCULAR = object()


def impedimento_para_anular_cobro(cobro, caja_reversa=_SIN_CALCULAR):
    """Por qué no se puede anular, o None: ya anulado, o entró a una caja ya cerrada y no hay
    una caja abierta para la reversa (DEC-113, DEC-166). `caja_reversa`, si ya se calculó con
    `caja_de_la_reversa`, evita repetir la consulta."""
    if cobro.estado == EstadoPagoCliente.ANULADO:
        return "El cobro ya está anulado."
    if not cobro.entra_a_caja:
        return None
    if caja_reversa is _SIN_CALCULAR:
        caja_reversa = caja_de_la_reversa(cobro)
    if caja_reversa is None:
        return MENSAJE_SIN_CAJA_PARA_REVERSA
    return None


def anular_cobro(usuario, cobro, motivo):
    """Anula con motivo: `ANULACION_PAGO` vuelve a sumar la deuda y, si entró a caja, un egreso
    `ANULACION_COBRO` en la caja de su ingreso si sigue abierta (DEC-113) o, si se cerró, en la
    caja abierta (DEC-166, DEC-178). Uno que no entró a caja se anula siempre. El cobro, su
    ingreso y la caja cerrada no se tocan.

    Bloquea caja, cobro y cliente, en ese orden (DEC-128).
    """
    _exigir_administrador(usuario, "anula cobros")
    motivo = _validar_motivo(motivo, "de la anulación")
    with transaction.atomic():
        caja = caja_para_reversa_de_cobro(cobro) if cobro.entra_a_caja else None
        cobro = PagoCliente.objects.select_for_update().get(pk=cobro.pk)
        if cobro.estado == EstadoPagoCliente.ANULADO:
            raise ValidationError("El cobro ya está anulado.", code="ya_anulado")
        cliente = bloquear_cliente(cobro.cliente_id)
        if caja is not None:
            registrar_reversa_cobro(cobro, usuario, motivo, caja)
        MovimientoCuentaCorriente.objects.create(
            # RI-15: el mismo cliente que el cobro.
            cliente=cliente,
            tipo=Tipo.ANULACION_PAGO,
            monto=cobro.monto,
            pago_cliente=cobro,
        )
        cobro.estado = EstadoPagoCliente.ANULADO
        cobro.anulado_en = timezone.now()
        cobro.anulado_por_usuario = usuario
        cobro.motivo_anulacion = motivo
        cobro.save(
            update_fields=[
                "estado",
                "anulado_en",
                "anulado_por_usuario",
                "motivo_anulacion",
                "actualizado_en",
            ]
        )
    return cobro


# CU-08 Gestionar cuentas corrientes: estado de cuenta (DEC-109, DEC-112, DEC-115, DEC-119;
# S-10, S-11). Solo el Administrador.


def cliente_con_cuenta(usuario, pk):
    """El cliente, activo o no, con saldo, deuda vencida, límite y disponible (CU-08)."""
    _exigir_administrador(usuario, "consulta el estado de cuenta")
    (cliente,) = con_cuenta([Cliente.objects.get(pk=pk)])
    return cliente


# Orden de registro de la cuenta: el saldo acumulado y los saldos del comprobante lo siguen
# (DEC-168, DEC-177). El id desempata dos movimientos de la misma fecha y hora.
ORDEN_DE_REGISTRO = [F("fecha_hora").asc(), F("pk").asc()]


def _con_signo():
    """El monto con su signo: lo que suma a la deuda, positivo; lo que la baja, negativo."""
    return Case(
        When(tipo__in=TIPOS_QUE_SUMAN, then=F("monto")),
        default=-F("monto"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def movimientos_de_cuenta(usuario, cliente):
    """Los movimientos del cliente, del más nuevo al más viejo (CU-08, RF-39), cada uno con el
    saldo después de él (`saldo_acumulado`, L17, DEC-168, DEC-177).

    El acumulado se calcula en la base sobre todos los movimientos, en orden de registro, así
    que es el mismo en cualquier página; el último coincide con el saldo del cliente. No se
    guarda (DEC-21).
    """
    _exigir_administrador(usuario, "consulta el estado de cuenta")
    return (
        MovimientoCuentaCorriente.objects.filter(cliente=cliente)
        .annotate(saldo_acumulado=Window(Sum(_con_signo()), order_by=ORDEN_DE_REGISTRO))
        .select_related("venta", "pago_cliente__medio_pago")
        .order_by("-fecha_hora", "-pk")
    )


# Comprobante del cobro (L16, DEC-167, DEC-185)


def _es_de_la_caja_del_dia(cobro):
    """El cobro entró a la caja abierta de hoy: la cajera lo puede reimprimir (DEC-185)."""
    if not cobro.entra_a_caja:
        return False
    caja = ingreso_de_cobro(cobro).caja
    return caja.estado == EstadoCaja.ABIERTA and not es_de_otro_dia(caja)


def puede_ver_comprobante(usuario, cobro):
    """El Administrador, de cualquier cobro; la cajera, de los cobros de la caja abierta de hoy
    (DEC-185). Los dueños no (DEC-134)."""
    if puede_gestionar(usuario):
        return True
    return usuario.rol == Rol.CAJERA and _es_de_la_caja_del_dia(cobro)


def comprobante_de_cobro(usuario, pk):
    """El cobro con lo que muestra su comprobante: `saldo_anterior` y `saldo_posterior`.

    Los saldos salen de los movimientos de la cuenta hasta el cobro, en orden de registro
    (DEC-167, DEC-177); no se guardan (DEC-21). PermissionDenied si el usuario no lo puede ver.
    """
    cobro = PagoCliente.objects.select_related(
        "cliente", "medio_pago", "usuario", "anulado_por_usuario"
    ).get(pk=pk)
    if not puede_ver_comprobante(usuario, cobro):
        raise PermissionDenied("Ese comprobante no se puede ver.")
    movimiento = MovimientoCuentaCorriente.objects.get(pago_cliente=cobro, tipo=Tipo.PAGO)
    hasta_el_cobro = Q(fecha_hora__lt=movimiento.fecha_hora) | Q(
        fecha_hora=movimiento.fecha_hora, pk__lte=movimiento.pk
    )
    posterior = MovimientoCuentaCorriente.objects.filter(
        hasta_el_cobro, cliente_id=cobro.cliente_id
    ).aggregate(saldo=Sum(_con_signo()))["saldo"]
    cobro.saldo_posterior = (posterior or CERO).quantize(CENTAVO)
    cobro.saldo_anterior = cobro.saldo_posterior + cobro.monto
    return cobro


def cobros_de_la_caja_del_dia(usuario):
    """Los cobros que entraron a la caja abierta de hoy, para que la cajera reimprima su
    comprobante (DEC-185); del último al primero."""
    if not puede_elegir(usuario):
        raise PermissionDenied("Solo el administrador y la cajera cobran cuentas corrientes.")
    caja = caja_abierta()
    if caja is None or es_de_otro_dia(caja):
        return PagoCliente.objects.none()
    return (
        PagoCliente.objects.filter(
            movimientocaja__caja=caja,
            movimientocaja__concepto=ConceptoMovimientoCaja.PAGO_CLIENTE,
        )
        .select_related("cliente", "medio_pago")
        .order_by("-fecha_hora", "-pk")
    )


def con_anulacion(movimientos):
    """Marca `anulado` en las ventas, cobros y saldos iniciales que tienen su movimiento inverso,
    aunque la anulación esté en otra página. `clientes` no importa `ventas` (R-4): una venta
    está anulada si tiene fecha de anulación (DEC-67)."""
    movimientos = list(movimientos)
    saldos = [m.pk for m in movimientos if m.tipo == Tipo.SALDO_INICIAL]
    anulados = set(
        MovimientoCuentaCorriente.objects.filter(saldo_inicial_id__in=saldos).values_list(
            "saldo_inicial_id", flat=True
        )
    )
    for movimiento in movimientos:
        if movimiento.tipo == Tipo.VENTA_FIADA:
            movimiento.anulado = movimiento.venta.anulada_en is not None
        elif movimiento.tipo == Tipo.PAGO:
            movimiento.anulado = movimiento.pago_cliente.estado == EstadoPagoCliente.ANULADO
        elif movimiento.tipo == Tipo.SALDO_INICIAL:
            movimiento.anulado = movimiento.pk in anulados
        else:
            movimiento.anulado = False
        movimiento.suma = movimiento.tipo in TIPOS_QUE_SUMAN
    return movimientos


def modificar_condiciones(usuario, cliente, limite_credito, observaciones):
    """Límite de crédito y observaciones desde el estado de cuenta (RF-41, DEC-108, DEC-112).

    Como en CU-12, un cliente dado de baja no se modifica: primero se reactiva.
    """
    _exigir_administrador(usuario, "modifica límites y condiciones")
    if not cliente.activo:
        raise ValidationError(
            f"{cliente} está dado de baja: para modificarlo, primero hay que reactivarlo.",
            code="cliente_inactivo",
        )
    cliente.limite_credito = limite_credito
    cliente.observaciones = (observaciones or "").strip()
    cliente.full_clean()
    cliente.save(update_fields=["limite_credito", "observaciones", "actualizado_en"])
    return cliente
