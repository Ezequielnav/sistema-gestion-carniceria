from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.comun.permisos import requiere_funcion
from apps.usuarios.forms import ContrasenaForm, IngresoForm, UsuarioForm
from apps.usuarios.services import (
    CAMPOS_EDITABLES,
    crear_usuario,
    desactivar,
    impedimento_para_desactivar,
    listar_usuarios,
    modificar_usuario,
    reactivar,
    restablecer_contrasena,
    tiene_panel,
    usuario_activo,
    usuario_desactivado,
)

# DEC-95: de a 25, como los demás listados.
POR_PAGINA = 25


class IngresarView(LoginView):
    """CU-10: inicio de sesión con sesiones de Django (D-06)."""

    template_name = "usuarios/ingresar.html"
    authentication_form = IngresoForm
    redirect_authenticated_user = True


class SalirView(LogoutView):
    """CU-10, A3: cierra la sesión (solo por POST) y vuelve al ingreso."""


def _buscar(funcion, pk):
    try:
        return funcion(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error


@requiere_funcion("Usuarios")
def usuarios(request):
    """CU-14: listado de activos; "Incluir desactivados" suma los demás (DEC-149)."""
    texto = request.GET.get("q", "").strip()
    incluir_inactivos = request.GET.get("inactivos") == "1"
    lista = listar_usuarios(request.user, texto, incluir_inactivos)
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    for usuario in pagina.object_list:
        usuario.con_panel = tiene_panel(usuario)
    return render(
        request,
        "usuarios/usuarios.html",
        {"pagina": pagina, "texto": texto, "incluir_inactivos": incluir_inactivos},
    )


def _guardar(request, form, operacion, mensaje):
    """Llama al servicio y pasa sus errores al formulario, junto al campo que corresponde."""
    if request.method == "POST" and form.is_valid():
        try:
            usuario = operacion(form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, mensaje.format(usuario=usuario))
            return redirect("usuarios:usuarios")
    return None


@requiere_funcion("Usuarios")
@require_http_methods(["GET", "POST"])
def nuevo(request):
    form = UsuarioForm(request.POST or None, es_alta=True)
    respuesta = _guardar(
        request,
        form,
        lambda datos: crear_usuario(request.user, datos, datos["password1"]),
        "Se dio de alta a «{usuario}».",
    )
    return respuesta or render(request, "usuarios/usuario_form.html", {"form": form})


@requiere_funcion("Usuarios")
@require_http_methods(["GET", "POST"])
def editar(request, pk):
    # Un usuario desactivado no se edita: primero se reactiva (como CU-12 y CU-13).
    usuario = _buscar(usuario_activo, pk)
    form = UsuarioForm(request.POST or None, initial=model_to_dict(usuario, CAMPOS_EDITABLES))
    respuesta = _guardar(
        request,
        form,
        lambda datos: modificar_usuario(request.user, usuario, datos),
        "Se guardaron los cambios de «{usuario}».",
    )
    if respuesta:
        return respuesta
    if request.method == "POST":
        usuario.refresh_from_db()
    return render(request, "usuarios/usuario_form.html", {"form": form, "usuario": usuario})


@requiere_funcion("Usuarios")
@require_http_methods(["GET", "POST"])
def baja(request, pk):
    """Desactivar con confirmación (DEC-135, DEC-149)."""
    usuario = _buscar(usuario_activo, pk)
    error = impedimento_para_desactivar(request.user, usuario)
    if request.method == "POST" and not error:
        try:
            desactivar(request.user, usuario)
        except ValidationError as rechazo:
            error = " ".join(rechazo.messages)
        else:
            messages.success(request, f"Se desactivó a «{usuario}».")
            return redirect("usuarios:usuarios")
    return render(request, "usuarios/usuario_baja.html", {"usuario": usuario, "error": error})


@requiere_funcion("Usuarios")
@require_POST
def reactivar_usuario(request, pk):
    usuario = _buscar(usuario_desactivado, pk)
    reactivar(request.user, usuario)
    messages.success(request, f"Se reactivó a «{usuario}».")
    return redirect("usuarios:usuarios")


@requiere_funcion("Usuarios")
@require_http_methods(["GET", "POST"])
def contrasena(request, pk):
    """Restablecer la contraseña de un usuario activo (DEC-151, DEC-156)."""
    usuario = _buscar(usuario_activo, pk)
    form = ContrasenaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            restablecer_contrasena(request.user, usuario, form.cleaned_data["password1"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            if usuario.pk == request.user.pk:
                # Su propia contraseña: la sesión sigue abierta.
                update_session_auth_hash(request, usuario)
            messages.success(request, f"Se cambió la contraseña de «{usuario}».")
            return redirect("usuarios:usuarios")
    return render(
        request,
        "usuarios/usuario_contrasena.html",
        {"form": form, "usuario": usuario, "con_panel": tiene_panel(usuario)},
    )
