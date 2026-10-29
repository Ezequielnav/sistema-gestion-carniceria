"""Reglas de CU-13 Gestionar proveedores (DEC-87, DEC-88).

Mismo patrón que CU-11: alta, modificación, baja lógica y reactivación, solo del
Administrador. El nombre repetido no se bloquea (DEC-87). R-6: este módulo puede usar
catálogo y caja, pero ellos nunca importan `proveedores`.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from apps.proveedores.models import Proveedor
from apps.usuarios.models import Rol

# Datos de contacto a confirmar (PR-31).
CAMPOS_EDITABLES = ["nombre", "telefono", "email"]


def puede_gestionar(usuario):
    """CU-13 es solo del Administrador (DEC-88); permiso doble con la vista (R-9)."""
    return usuario.rol == Rol.ADMINISTRADOR


def _exigir_permiso(usuario):
    if not puede_gestionar(usuario):
        raise PermissionDenied("Solo el administrador gestiona proveedores.")


def listar_proveedores(usuario, texto="", incluir_inactivos=False):
    """Por nombre, teléfono o email (contiene), ordenados por nombre; los dados de baja solo
    si se piden (DEC-87)."""
    _exigir_permiso(usuario)
    proveedores = Proveedor.objects.order_by("nombre", "pk")
    if not incluir_inactivos:
        proveedores = proveedores.filter(activo=True)
    texto = texto.strip()
    if texto:
        proveedores = proveedores.filter(
            Q(nombre__icontains=texto) | Q(telefono__icontains=texto) | Q(email__icontains=texto)
        )
    return proveedores


def proveedor_editable(pk):
    """Proveedor activo; uno dado de baja primero se reactiva. Proveedor.DoesNotExist si no."""
    return Proveedor.objects.get(pk=pk, activo=True)


def proveedor_dado_de_baja(pk):
    """Proveedor inactivo, para reactivarlo. Proveedor.DoesNotExist si no lo es."""
    return Proveedor.objects.get(pk=pk, activo=False)


def _guardar(proveedor, datos):
    for campo in CAMPOS_EDITABLES:
        setattr(proveedor, campo, (datos.get(campo) or "").strip())
    proveedor.full_clean()
    proveedor.save()
    return proveedor


def crear_proveedor(usuario, datos):
    _exigir_permiso(usuario)
    return _guardar(Proveedor(), datos)


def modificar_proveedor(usuario, proveedor, datos):
    _exigir_permiso(usuario)
    return _guardar(proveedor, datos)


def dar_de_baja(usuario, proveedor):
    """Baja lógica: sus ingresos y pagos no cambian (RI-11). Un proveedor dado de baja no
    recibe ingresos ni pagos (S-1)."""
    _exigir_permiso(usuario)
    proveedor.activo = False
    proveedor.save(update_fields=["activo", "actualizado_en"])
    return proveedor


def reactivar(usuario, proveedor):
    """Vuelve a activar un proveedor dado de baja (DEC-87, como DEC-85)."""
    _exigir_permiso(usuario)
    proveedor.activo = True
    proveedor.save(update_fields=["activo", "actualizado_en"])
    return proveedor
