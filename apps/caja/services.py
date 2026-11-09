"""Reglas de CU-02 Abrir caja, CU-03 Cerrar caja y SC-02 Registrar movimiento de caja."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.caja.models import (
    Caja,
    CierreCajaDetalle,
    ConceptoMovimientoCaja,
    EstadoCaja,
    MedioPago,
    MovimientoCaja,
    TipoMovimientoCaja,
    Turno,
)
from apps.comun.models import pesos
from apps.usuarios.models import Rol


def cajas_abiertas():
    return list(Caja.objects.filter(estado=EstadoCaja.ABIERTA).order_by("fecha", "turno"))


def caja_abierta():
    """La única caja abierta (DEC-39), o None."""
    return Caja.objects.filter(estado=EstadoCaja.ABIERTA).select_related("usuario").first()


def es_de_otro_dia(caja):
    """La caja es de una fecha anterior a hoy: no recibe ventas (DEC-50)."""
    return caja.fecha != timezone.localdate()


def puede_abrir(usuario):
    """CU-02: solo la cajera (matriz de actores de 04)."""
    return usuario.rol == Rol.CAJERA


def turnos_libres():
    """Turnos que se pueden abrir: los dos si no hay caja abierta (DEC-83)."""
    return list(Turno) if caja_abierta() is None else []


def _describir(caja):
    return f"la del turno {caja.get_turno_display().lower()} del {caja.fecha:%d/%m/%Y}"


def _ya_abierta(caja):
    # Sin caja: la que chocó al abrir ya se cerró entre medio (carrera entre dos cajeras).
    cual = f": {_describir(caja)}" if caja is not None else ""
    return ValidationError(
        f"Ya hay una caja abierta{cual}. Hay que cerrarla antes de abrir otra.",
        code="caja_abierta",
    )


def abrir_caja(usuario, turno, monto_inicial=None):
    """Abre la caja de hoy en el turno elegido (RF-04, RF-05, RN-01, DEC-38, DEC-83).

    El fondo de cambio vacío se guarda 0 (DEC-38).
    """
    if not puede_abrir(usuario):
        raise PermissionDenied("Solo la cajera puede abrir la caja.")
    caja = Caja(
        fecha=timezone.localdate(),
        turno=turno,
        usuario=usuario,
        monto_inicial=Decimal("0") if monto_inicial is None else monto_inicial,
    )
    # Turno válido y fondo no negativo (RN-02, RI-16); las restricciones van aparte.
    caja.full_clean(validate_constraints=False)
    abierta = caja_abierta()
    if abierta is not None:
        raise _ya_abierta(abierta)
    try:
        # Savepoint: si otra cajera abrió a la vez, la base lo rechaza (RI-01).
        with transaction.atomic():
            caja.save()
    except IntegrityError as error:
        if "caja_una_sola_abierta" in str(error):
            raise _ya_abierta(caja_abierta()) from error
        raise
    return caja


def registrar_ingreso_venta(venta):
    """SC-02: el ingreso de una venta en su caja, por el total y con su medio de pago.

    RN-04, RI-04 y RI-13. Una caja cerrada no recibe movimientos (RN-03, RI-02).
    """
    if venta.caja.estado != EstadoCaja.ABIERTA:
        raise ValidationError("La caja está cerrada: no recibe movimientos.", code="caja_cerrada")
    return MovimientoCaja.objects.create(
        caja=venta.caja,
        fecha_hora=venta.fecha_hora,
        tipo=TipoMovimientoCaja.INGRESO,
        monto=venta.monto_total,
        medio_pago=venta.medio_pago,
        concepto=ConceptoMovimientoCaja.VENTA,
        venta=venta,
        usuario=venta.usuario,
    )


def registrar_reversa_venta(venta, usuario, motivo):
    """SC-02: el egreso que revierte el ingreso de una venta anulada (DEC-45, DEC-68).

    Se llama dentro de la transacción de la anulación, con la caja ya bloqueada. Si la venta
    fue en efectivo, no puede dejar el efectivo esperado por debajo de 0 (DEC-69).
    """
    caja = venta.caja
    if caja.estado != EstadoCaja.ABIERTA:
        raise ValidationError("La caja está cerrada: no recibe movimientos.", code="caja_cerrada")
    medio = venta.medio_pago
    if medio.es_efectivo:
        disponible = _esperado(caja, medio)
        if venta.monto_total > disponible:
            raise ValidationError(
                f"En la caja hay $ {disponible:.2f} en efectivo: no alcanza para devolver "
                f"$ {venta.monto_total:.2f}.",
                code="sin_efectivo_suficiente",
            )
    return MovimientoCaja.objects.create(
        caja=caja,
        tipo=TipoMovimientoCaja.EGRESO,
        monto=venta.monto_total,
        medio_pago=medio,
        concepto=ConceptoMovimientoCaja.ANULACION,
        venta=venta,
        usuario=usuario,
        descripcion=motivo,
    )


# Egresos "otros" (DEC-43, DEC-57, DEC-58)


def efectivo():
    """El medio de pago en efectivo (DEC-55)."""
    medio = MedioPago.objects.filter(es_efectivo=True).first()
    if medio is None:
        raise ValidationError(
            "No hay un medio de pago marcado como efectivo. Hay que marcarlo en el panel.",
            code="sin_efectivo",
        )
    return medio


def _caja_abierta_bloqueada():
    """La caja abierta, con su fila bloqueada hasta terminar la operación (RNF-10)."""
    caja = Caja.objects.select_for_update().filter(estado=EstadoCaja.ABIERTA).first()
    if caja is None:
        raise ValidationError("No hay una caja abierta.", code="sin_caja")
    return caja


# Reversas de cobros y pagos (DEC-92, DEC-113; con la caja cerrada, DEC-166 y DEC-178)

MENSAJE_SIN_CAJA_PARA_REVERSA = (
    "La caja de origen ya se cerró y no hay una caja abierta para registrar la reversa: abrí "
    "la caja para corregirlo."
)


def caja_que_recibe_la_reversa(caja_origen):
    """Sin bloquear, para mostrarla: la caja de origen si sigue abierta (aunque sea de otro día,
    DEC-72); si se cerró, la caja abierta, que también puede ser de otro día (DEC-178); o None
    si no hay ninguna. Una caja cerrada nunca recibe la reversa (RN-03)."""
    if caja_origen.estado == EstadoCaja.ABIERTA:
        return caja_origen
    return caja_abierta()


def _caja_para_reversa_bloqueada(caja_origen_id):
    """La caja de `caja_que_recibe_la_reversa`, bloqueada (DEC-128: primero la caja)."""
    caja = Caja.objects.select_for_update().get(pk=caja_origen_id)
    if caja.estado == EstadoCaja.ABIERTA:
        return caja
    abierta = Caja.objects.select_for_update().filter(estado=EstadoCaja.ABIERTA).first()
    if abierta is None:
        raise ValidationError(MENSAJE_SIN_CAJA_PARA_REVERSA, code="sin_caja_para_reversa")
    return abierta


def anulaciones(caja):
    """Reversas de ventas anuladas de la caja, con su venta (DEC-77)."""
    return list(
        MovimientoCaja.objects.filter(caja=caja, concepto=ConceptoMovimientoCaja.ANULACION)
        .select_related("venta", "medio_pago")
        .order_by("fecha_hora", "pk")
    )


def movimientos_de_pagos_a_proveedores(caja):
    """Egresos de pagos a proveedores y sus reversas, para explicar lo esperado en el cierre."""
    return list(
        MovimientoCaja.objects.filter(
            caja=caja,
            concepto__in=[
                ConceptoMovimientoCaja.PAGO_PROVEEDOR,
                ConceptoMovimientoCaja.ANULACION_PAGO,
            ],
        )
        .select_related("pago_proveedor__proveedor", "medio_pago")
        .order_by("fecha_hora", "pk")
    )


def egresos_otros(caja):
    return list(
        MovimientoCaja.objects.filter(
            caja=caja, tipo=TipoMovimientoCaja.EGRESO, concepto=ConceptoMovimientoCaja.OTRO
        ).order_by("fecha_hora", "pk")
    )


def registrar_egreso_otro(usuario, monto, descripcion):
    """SC-02: gasto o retiro en efectivo de la caja abierta, con descripción (DEC-43, RI-13)."""
    if not puede_abrir(usuario):
        raise PermissionDenied("Solo la cajera registra egresos de caja.")
    descripcion = (descripcion or "").strip()
    errores = {}
    if monto is None or monto <= 0:
        errores["monto"] = "El monto tiene que ser mayor a 0."
    if not descripcion:
        errores["descripcion"] = "Contá en qué se usó el efectivo."
    if errores:
        raise ValidationError(errores)
    with transaction.atomic():
        caja = _caja_abierta_bloqueada()
        medio = efectivo()
        disponible = _esperado(caja, medio)
        if monto > disponible:
            # DEC-57: no sale más efectivo del que hay.
            raise ValidationError(
                {"monto": f"En la caja hay $ {disponible:.2f} en efectivo: no alcanza."},
                code="sin_efectivo_suficiente",
            )
        return MovimientoCaja.objects.create(
            caja=caja,
            tipo=TipoMovimientoCaja.EGRESO,
            monto=monto,
            medio_pago=medio,
            concepto=ConceptoMovimientoCaja.OTRO,
            usuario=usuario,
            descripcion=descripcion,
        )


# SC-02 para CU-07: pago a proveedor en efectivo y su reversa (R-3, DEC-80, DEC-92).
# Comparten con el egreso "otro" y el cierre el bloqueo de la caja y el control de efectivo.


def efectivo_disponible():
    """Efectivo esperado de la caja abierta de hoy, o None si no se puede pagar en efectivo."""
    caja = caja_abierta()
    medio = MedioPago.objects.filter(es_efectivo=True).first()
    if caja is None or medio is None or es_de_otro_dia(caja):
        return None
    return _esperado(caja, medio)


def registrar_egreso_pago_proveedor(pago, usuario):
    """Egreso `PAGO_PROVEEDOR` de un pago que sale de la caja abierta del día (DEC-80, DEC-106).

    Va dentro de la transacción del pago. A nombre de quien registra, aunque la caja la haya
    abierto otro usuario. Sin caja abierta, con la de otro día (como DEC-50) o sin efectivo
    suficiente (CU-07 A1, como DEC-57), se rechaza mostrando el máximo.
    """
    caja = _caja_abierta_bloqueada()
    if es_de_otro_dia(caja):
        raise ValidationError(
            "La caja abierta es de otro día: hay que cerrarla y abrir la de hoy para pagar en "
            "efectivo.",
            code="caja_de_otro_dia",
        )
    medio = efectivo()
    disponible = _esperado(caja, medio)
    if pago.monto > disponible:
        raise ValidationError(
            {
                "monto": f"En la caja hay {pesos(max(disponible, Decimal('0')))} en efectivo: "
                "ese es el máximo que se puede pagar."
            },
            code="sin_efectivo_suficiente",
        )
    return MovimientoCaja.objects.create(
        caja=caja,
        fecha_hora=pago.fecha_hora,
        tipo=TipoMovimientoCaja.EGRESO,
        monto=pago.monto,
        medio_pago=medio,
        concepto=ConceptoMovimientoCaja.PAGO_PROVEEDOR,
        pago_proveedor=pago,
        usuario=usuario,
    )


def egreso_de_pago(pago):
    """El egreso de caja de un pago, o None si no salió de caja (DEC-106)."""
    return (
        MovimientoCaja.objects.filter(
            pago_proveedor=pago, concepto=ConceptoMovimientoCaja.PAGO_PROVEEDOR
        )
        .select_related("caja")
        .first()
    )


def caja_para_reversa_de_pago(pago):
    """La caja que recibe la reversa del pago, bloqueada: la de su egreso si sigue abierta
    (DEC-92); si se cerró, la caja abierta (DEC-166, DEC-178). Sin ninguna, se rechaza."""
    return _caja_para_reversa_bloqueada(egreso_de_pago(pago).caja_id)


def registrar_reversa_pago_proveedor(pago, usuario, motivo, caja):
    """Ingreso `ANULACION_PAGO` que revierte el egreso de un pago anulado (DEC-92).

    En la caja ya bloqueada con `caja_para_reversa_de_pago`: la del egreso o, si se cerró, la
    caja abierta (DEC-166). El egreso no se toca; un pago tiene a lo sumo una reversa (la base
    lo exige).
    """
    egreso = egreso_de_pago(pago)
    return MovimientoCaja.objects.create(
        caja=caja,
        tipo=TipoMovimientoCaja.INGRESO,
        monto=egreso.monto,
        medio_pago=egreso.medio_pago,
        concepto=ConceptoMovimientoCaja.ANULACION_PAGO,
        pago_proveedor=pago,
        usuario=usuario,
        descripcion=motivo,
    )


# SC-02 para CU-04: ingreso de un cobro a cliente y su reversa (R-1, DEC-110, DEC-113).
# Caja no conoce a `clientes` (R-4): recibe el cobro y usa solo sus campos.


def caja_del_dia_bloqueada():
    """La caja abierta de hoy, bloqueada (DEC-128: primero la caja). Sin caja abierta, o con la
    de otro día (como DEC-50), se rechaza."""
    caja = _caja_abierta_bloqueada()
    if es_de_otro_dia(caja):
        raise ValidationError(
            "La caja abierta es de otro día: hay que cerrarla y abrir la de hoy.",
            code="caja_de_otro_dia",
        )
    return caja


def hay_caja_del_dia():
    """Si hay una caja abierta de hoy, para ofrecer "Entra a la caja abierta" (S-6)."""
    caja = caja_abierta()
    return caja is not None and not es_de_otro_dia(caja)


def registrar_ingreso_cobro(pago, usuario, caja):
    """Ingreso `PAGO_CLIENTE` del cobro con su medio, en la caja del día ya bloqueada (RN-04)."""
    return MovimientoCaja.objects.create(
        caja=caja,
        fecha_hora=pago.fecha_hora,
        tipo=TipoMovimientoCaja.INGRESO,
        monto=pago.monto,
        medio_pago=pago.medio_pago,
        concepto=ConceptoMovimientoCaja.PAGO_CLIENTE,
        pago_cliente=pago,
        usuario=usuario,
    )


def ingreso_de_cobro(pago):
    """El ingreso de caja de un cobro, o None si no entró a caja (DEC-110)."""
    return (
        MovimientoCaja.objects.filter(
            pago_cliente=pago, concepto=ConceptoMovimientoCaja.PAGO_CLIENTE
        )
        .select_related("caja", "medio_pago")
        .first()
    )


def caja_para_reversa_de_cobro(pago):
    """La caja que recibe la reversa del cobro, bloqueada: la de su ingreso si sigue abierta,
    aunque sea de otro día (DEC-113, DEC-72); si se cerró, la caja abierta (DEC-166, DEC-178).
    Sin ninguna, se rechaza."""
    return _caja_para_reversa_bloqueada(ingreso_de_cobro(pago).caja_id)


def registrar_reversa_cobro(pago, usuario, motivo, caja):
    """Egreso `ANULACION_COBRO` que revierte el ingreso de un cobro anulado (DEC-113).

    En la caja ya bloqueada con `caja_para_reversa_de_cobro`: la del ingreso o, si se cerró, la
    caja abierta (DEC-166). En efectivo no puede dejar el efectivo esperado de esa caja por
    debajo de 0 (DEC-69). El ingreso no se toca.
    """
    ingreso = ingreso_de_cobro(pago)
    medio = ingreso.medio_pago
    if medio.es_efectivo:
        disponible = _esperado(caja, medio)
        if ingreso.monto > disponible:
            raise ValidationError(
                f"En la caja hay {pesos(max(disponible, Decimal('0')))} en efectivo: no alcanza "
                f"para devolver {pesos(ingreso.monto)}.",
                code="sin_efectivo_suficiente",
            )
    return MovimientoCaja.objects.create(
        caja=caja,
        tipo=TipoMovimientoCaja.EGRESO,
        monto=ingreso.monto,
        medio_pago=medio,
        concepto=ConceptoMovimientoCaja.ANULACION_COBRO,
        pago_cliente=pago,
        usuario=usuario,
        descripcion=motivo,
    )


def movimientos_de_cobros(caja):
    """Cobros a clientes y sus reversas, para explicar lo esperado en el cierre (S-8)."""
    return list(
        MovimientoCaja.objects.filter(
            caja=caja,
            concepto__in=[
                ConceptoMovimientoCaja.PAGO_CLIENTE,
                ConceptoMovimientoCaja.ANULACION_COBRO,
            ],
        )
        .select_related("pago_cliente__cliente", "medio_pago")
        .order_by("fecha_hora", "pk")
    )


# CU-03 Cerrar caja (RF-07, RF-08, RF-09, RI-10, DEC-38, DEC-40, DEC-56)


def _esperado(caja, medio):
    """Ingresos menos egresos del medio en la caja; el efectivo suma el fondo (DEC-38)."""
    totales = MovimientoCaja.objects.filter(caja=caja, medio_pago=medio).aggregate(
        ingresos=Sum("monto", filter=Q(tipo=TipoMovimientoCaja.INGRESO)),
        egresos=Sum("monto", filter=Q(tipo=TipoMovimientoCaja.EGRESO)),
    )
    esperado = (totales["ingresos"] or Decimal("0")) - (totales["egresos"] or Decimal("0"))
    if medio.es_efectivo:
        esperado += caja.monto_inicial or Decimal("0")
    return esperado


def medios_del_cierre(caja):
    """Activos que ingresan a caja, más los que tengan movimientos en esta caja (DEC-56)."""
    return list(
        MedioPago.objects.filter(Q(activo=True, ingresa_a_caja=True) | Q(movimientocaja__caja=caja))
        .distinct()
        .order_by("pk")
    )


def resumen_de_cierre(caja):
    """Lo esperado por medio de pago: lista de (medio, esperado)."""
    return [(medio, _esperado(caja, medio)) for medio in medios_del_cierre(caja)]


def cerrar_caja(usuario, contados, observacion=""):
    """Cierra la caja abierta con lo contado por medio (`contados`: id de medio -> monto).

    Guarda esperado y contado por medio (la diferencia no se guarda, RI-10), exige motivo
    si alguna diferencia no es cero (DEC-40) y bloquea la caja (RN-03, RI-02).
    """
    if not puede_abrir(usuario):
        raise PermissionDenied("Solo la cajera cierra la caja.")
    observacion = (observacion or "").strip()
    with transaction.atomic():
        caja = _caja_abierta_bloqueada()
        resumen = resumen_de_cierre(caja)
        errores = {}
        for medio, _ in resumen:
            contado = contados.get(medio.pk)
            if contado is None:
                errores[f"contado_{medio.pk}"] = f"Falta lo contado en {medio}."
            elif contado < 0:
                errores[f"contado_{medio.pk}"] = "No puede ser negativo."
        if errores:
            raise ValidationError(errores)
        if any(contados[medio.pk] != esperado for medio, esperado in resumen) and not observacion:
            raise ValidationError(
                {"observacion": "Hay diferencias: escribí el motivo para poder cerrar."},
                code="falta_motivo",
            )
        CierreCajaDetalle.objects.bulk_create(
            CierreCajaDetalle(
                caja=caja,
                medio_pago=medio,
                monto_sistema=esperado,
                monto_contado=contados[medio.pk],
            )
            for medio, esperado in resumen
        )
        caja.estado = EstadoCaja.CERRADA
        caja.cerrada_en = timezone.now()
        caja.cerrada_por_usuario = usuario
        caja.observacion_cierre = observacion
        caja.save()
    return caja


def puede_ver_cierre(usuario):
    """DEC-59: cajera, Administrador y Dueños."""
    return usuario.is_authenticated and usuario.rol in (Rol.CAJERA, Rol.ADMINISTRADOR, Rol.DUENIO)


def caja_cerrada(pk):
    """La caja cerrada para su reporte; Caja.DoesNotExist si no existe o sigue abierta."""
    return Caja.objects.select_related("usuario", "cerrada_por_usuario").get(
        pk=pk, estado=EstadoCaja.CERRADA
    )


def detalle_de_cierre(caja):
    """Por medio: (medio, esperado, contado, diferencia). La diferencia se calcula (RI-10)."""
    return [
        (d.medio_pago, d.monto_sistema, d.monto_contado, d.monto_contado - d.monto_sistema)
        for d in caja.cierrecajadetalle_set.select_related("medio_pago").order_by("medio_pago")
    ]


# Medios de pago, solo del Administrador y sin borrado (DEC-155, L18).

# DEC-55.
MEDIO_EFECTIVO_ACTIVO = "El efectivo no se desactiva: lo usan el fondo de cambio y los egresos."


def puede_gestionar_medios(usuario):
    return usuario.is_authenticated and usuario.rol == Rol.ADMINISTRADOR


def _exigir_medios(usuario):
    if not puede_gestionar_medios(usuario):
        raise PermissionDenied("Solo el administrador gestiona los medios de pago.")


def listar_medios(usuario):
    """Activos primero, después por nombre."""
    _exigir_medios(usuario)
    return MedioPago.objects.order_by("-activo", "nombre", "pk")


def _guardar_medio(medio):
    medio.nombre = (medio.nombre or "").strip()
    # Nombre único sin mayúsculas, un solo efectivo y un solo medio que no ingresa a caja
    # (DEC-41, DEC-55): full_clean da el mensaje de cada restricción.
    medio.full_clean()
    medio.save()
    return medio


def crear_medio(usuario, nombre, ingresa_a_caja, es_efectivo):
    """Las marcas se fijan en el alta y después no cambian (DEC-155)."""
    _exigir_medios(usuario)
    medio = MedioPago(nombre=nombre, ingresa_a_caja=ingresa_a_caja, es_efectivo=es_efectivo)
    return _guardar_medio(medio)


def modificar_medio(usuario, medio, nombre):
    """Solo el nombre: cambiar las marcas de un medio usado cambiaría cómo se leen los
    cierres ya hechos (DEC-155)."""
    _exigir_medios(usuario)
    medio.nombre = nombre
    return _guardar_medio(medio)


def cambiar_activo(usuario, medio, activo):
    """Activar o desactivar; un medio desactivado deja de ofrecerse en la venta, el cobro y
    los pagos, y sus movimientos siguen como están. El efectivo no se desactiva."""
    _exigir_medios(usuario)
    if not activo and medio.es_efectivo:
        raise ValidationError(MEDIO_EFECTIVO_ACTIVO)
    medio.activo = activo
    medio.save(update_fields=["activo", "actualizado_en"])
    return medio
