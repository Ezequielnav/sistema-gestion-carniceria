"""CU-14 Gestionar usuarios (RF-03; DEC-135, DEC-149 a DEC-151, DEC-156).

Un usuario por persona, sin autorregistro: solo el Administrador da de alta, edita,
desactiva, reactiva y restablece contraseñas. Un usuario nunca se borra (DEC-135).
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from apps.usuarios.models import Rol, Usuario

CAMPOS_EDITABLES = [
    "username",
    "nombre_completo",
    "telefono",
    "email",
    "rol",
    "puede_crear_productos",
]
# DEC-156.
SOLO_CON_MANAGE = (
    "Este usuario entra al panel de administración: lo gestiona el soporte técnico, no esta "
    "pantalla."
)


def puede_gestionar(usuario):
    """CU-14 es solo del Administrador (DEC-135); permiso doble con la vista."""
    return usuario.is_authenticated and usuario.rol == Rol.ADMINISTRADOR


def _exigir_permiso(usuario):
    if not puede_gestionar(usuario):
        raise PermissionDenied("Solo el administrador gestiona usuarios.")


def tiene_panel(usuario):
    """El superusuario técnico, o cualquiera con acceso al panel (DEC-150, DEC-156)."""
    return usuario.is_staff or usuario.is_superuser


def listar_usuarios(usuario, texto="", incluir_inactivos=False):
    """Por usuario o nombre (contiene), ordenados por usuario; los desactivados solo si se
    piden (DEC-149)."""
    _exigir_permiso(usuario)
    usuarios = Usuario.objects.order_by("username", "pk")
    if not incluir_inactivos:
        usuarios = usuarios.filter(is_active=True)
    texto = texto.strip()
    if texto:
        usuarios = usuarios.filter(
            Q(username__icontains=texto) | Q(nombre_completo__icontains=texto)
        )
    return usuarios


def usuario_activo(pk):
    """Usuario activo; uno desactivado primero se reactiva. Usuario.DoesNotExist si no."""
    return Usuario.objects.get(pk=pk, is_active=True)


def usuario_desactivado(pk):
    """Usuario desactivado, para reactivarlo. Usuario.DoesNotExist si no lo es."""
    return Usuario.objects.get(pk=pk, is_active=False)


def _asignar(usuario, datos):
    for campo in CAMPOS_EDITABLES:
        valor = datos.get(campo)
        setattr(usuario, campo, valor.strip() if isinstance(valor, str) else valor)
    # RN-05: el permiso de alta de productos es solo de la cajera.
    if usuario.rol != Rol.CAJERA:
        usuario.puede_crear_productos = False


def _validar_contrasena(usuario, contrasena):
    try:
        validate_password(contrasena, usuario)
    except ValidationError as error:
        raise ValidationError({"password1": error.messages}) from error


def _bloquear_administradores_activos():
    """Bloquea a los Administradores activos: dos operaciones al mismo tiempo no pueden
    dejar al sistema sin ninguno (DEC-150)."""
    return list(
        Usuario.objects.select_for_update()
        .filter(rol=Rol.ADMINISTRADOR, is_active=True)
        .values_list("pk", flat=True)
    )


def _deja_sin_administrador(objetivo):
    activos = _bloquear_administradores_activos()
    return objetivo.rol == Rol.ADMINISTRADOR and activos == [objetivo.pk]


def crear_usuario(usuario, datos, contrasena):
    """Alta con rol y contraseña inicial (DEC-149). Nunca entra al panel (DEC-150)."""
    _exigir_permiso(usuario)
    nuevo = Usuario(is_staff=False, is_superuser=False)
    _asignar(nuevo, datos)
    nuevo.full_clean(exclude=["password"])
    _validar_contrasena(nuevo, contrasena)
    nuevo.set_password(contrasena)
    nuevo.save()
    return nuevo


def modificar_usuario(usuario, objetivo, datos):
    """Edita datos y rol, no la contraseña (DEC-149). Nadie se quita el rol a sí mismo, el
    rol de un usuario con panel no cambia y siempre queda un Administrador (DEC-150, DEC-156).
    """
    _exigir_permiso(usuario)
    with transaction.atomic():
        objetivo = Usuario.objects.select_for_update().get(pk=objetivo.pk)
        if datos.get("rol") != objetivo.rol:
            if objetivo.pk == usuario.pk:
                raise ValidationError({"rol": "No podés cambiar tu propio rol."})
            if tiene_panel(objetivo):
                raise ValidationError({"rol": SOLO_CON_MANAGE})
            if _deja_sin_administrador(objetivo):
                raise ValidationError({"rol": "Tiene que quedar al menos un Administrador activo."})
        _asignar(objetivo, datos)
        objetivo.full_clean(exclude=["password"])
        objetivo.save()
    return objetivo


def impedimento_para_desactivar(usuario, objetivo):
    """Por qué no se puede desactivar, o None (DEC-150, DEC-156). Se vuelve a validar al
    desactivar, con el bloqueo."""
    if objetivo.pk == usuario.pk:
        return "No podés desactivar tu propio usuario."
    if tiene_panel(objetivo):
        return SOLO_CON_MANAGE
    return None


def desactivar(usuario, objetivo):
    """Baja lógica (DEC-135): no puede ingresar y su sesión abierta deja de valer en el
    próximo pedido (DEC-151). Sus operaciones lo siguen referenciando (RNF-09)."""
    _exigir_permiso(usuario)
    motivo = impedimento_para_desactivar(usuario, objetivo)
    if motivo:
        raise ValidationError(motivo)
    with transaction.atomic():
        if _deja_sin_administrador(objetivo):
            raise ValidationError("Tiene que quedar al menos un Administrador activo.")
        objetivo.is_active = False
        objetivo.save(update_fields=["is_active", "actualizado_en"])
    return objetivo


def reactivar(usuario, objetivo):
    """Vuelve a habilitar a un usuario desactivado (DEC-149)."""
    _exigir_permiso(usuario)
    objetivo.is_active = True
    objetivo.save(update_fields=["is_active", "actualizado_en"])
    return objetivo


def restablecer_contrasena(usuario, objetivo, contrasena):
    """El Administrador escribe una contraseña nueva, sin email (DEC-151). La de un usuario
    con panel se cambia con manage.py (DEC-156)."""
    _exigir_permiso(usuario)
    if tiene_panel(objetivo):
        raise ValidationError(SOLO_CON_MANAGE)
    _validar_contrasena(objetivo, contrasena)
    objetivo.set_password(contrasena)
    objetivo.save(update_fields=["password", "actualizado_en"])
    return objetivo
