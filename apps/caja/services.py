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
from apps.usuarios.models import Rol


def cajas_abiertas():
    return list(Caja.objects.filter(estado=EstadoCaja.ABIERTA).order_by("fecha", "turno"))


def caja_abierta():
    """La única caja abierta (DEC-39), o None."""
    return Caja.objects.filter(estado=EstadoCaja.ABIERTA).select_related("usuario").first()


def puede_abrir(usuario):
    """CU-02: solo la cajera (matriz de actores de 04)."""
    return usuario.rol == Rol.CAJERA


def turnos_libres(fecha):
    """Turnos que todavía no tuvieron caja en la fecha: un turno no se reabre (DEC-39)."""
    usados = set(Caja.objects.filter(fecha=fecha).values_list("turno", flat=True))
    return [turno for turno in Turno if turno not in usados]


def _describir(caja):
    return f"la del turno {caja.get_turno_display().lower()} del {caja.fecha:%d/%m/%Y}"


def _ya_abierta(caja):
    # Sin caja: la que chocó al abrir ya se cerró entre medio (carrera entre dos cajeras).
    cual = f": {_describir(caja)}" if caja is not None else ""
    return ValidationError(
        f"Ya hay una caja abierta{cual}. Hay que cerrarla antes de abrir otra.",
        code="caja_abierta",
    )


def _turno_usado(turno):
    return ValidationError(
        {"turno": f"El turno {Turno(turno).label.lower()} ya tuvo una caja hoy y no se reabre."},
        code="turno_usado",
    )


def abrir_caja(usuario, turno, monto_inicial=None):
    """Abre la caja de hoy en el turno elegido (RF-04, RF-05, RN-01, DEC-38, DEC-39).

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
    if turno not in turnos_libres(caja.fecha):
        raise _turno_usado(turno)
    try:
        # Savepoint: si otra cajera abrió a la vez, la base lo rechaza (RI-01).
        with transaction.atomic():
            caja.save()
    except IntegrityError as error:
        if "caja_una_sola_abierta" in str(error):
            raise _ya_abierta(caja_abierta()) from error
        if "caja_unica_por_fecha_turno" in str(error):
            raise _turno_usado(turno) from error
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


def anulaciones(caja):
    """Reversas de ventas anuladas de la caja, con su venta (DEC-77)."""
    return list(
        MovimientoCaja.objects.filter(caja=caja, concepto=ConceptoMovimientoCaja.ANULACION)
        .select_related("venta", "medio_pago")
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


def detalle_de_cierre(caja):
    """Por medio: (medio, esperado, contado, diferencia). La diferencia se calcula (RI-10)."""
    return [
        (d.medio_pago, d.monto_sistema, d.monto_contado, d.monto_contado - d.monto_sistema)
        for d in caja.cierrecajadetalle_set.select_related("medio_pago").order_by("medio_pago")
    ]
