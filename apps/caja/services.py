"""Reglas de CU-02 Abrir caja por turno y SC-02 Registrar movimiento de caja."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.caja.models import (
    Caja,
    ConceptoMovimientoCaja,
    EstadoCaja,
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
    return ValidationError(
        f"Ya hay una caja abierta: {_describir(caja)}. Hay que cerrarla antes de abrir otra.",
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
