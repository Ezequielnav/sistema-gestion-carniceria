from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.caja.services import hay_caja_del_dia, ingreso_de_cobro
from apps.clientes.forms import AnularCobroForm, ClienteForm, CobroForm
from apps.clientes.services import (
    CAMPOS_EDITABLES,
    anular_cobro,
    buscar_para_elegir,
    cliente_dado_de_baja,
    cliente_editable,
    cliente_para_elegir,
    cobro_con_detalles,
    con_cuenta,
    crear_cliente,
    dar_de_baja,
    impedimento_para_anular_cobro,
    listar_clientes,
    modificar_cliente,
    puede_gestionar,
    reactivar,
    registrar_cobro,
    saldo,
)
from apps.comun.models import pesos
from apps.comun.permisos import requiere_funcion

# DEC-118: de a 25, como productos y proveedores (DEC-95).
POR_PAGINA = 25


def _buscar(funcion, pk):
    try:
        return funcion(pk)
    except ObjectDoesNotExist as error:
        raise Http404 from error


@requiere_funcion("Clientes")
def clientes(request):
    """CU-12: listado con saldo, límite y deuda vencida (S-7); "Incluir dados de baja" suma los
    inactivos y "Solo con deuda vencida" filtra (DEC-109)."""
    texto = request.GET.get("q", "").strip()
    incluir_inactivos = request.GET.get("inactivos") == "1"
    solo_vencidos = request.GET.get("vencidos") == "1"
    lista = listar_clientes(request.user, texto, incluir_inactivos, solo_vencidos)
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    pagina.object_list = con_cuenta(pagina.object_list)
    return render(
        request,
        "clientes/clientes.html",
        {
            "pagina": pagina,
            "texto": texto,
            "incluir_inactivos": incluir_inactivos,
            "solo_vencidos": solo_vencidos,
        },
    )


def _guardar_con(request, form, operacion, mensaje):
    """Llama al servicio y pasa sus errores al formulario, junto al campo que corresponde."""
    if request.method == "POST" and form.is_valid():
        try:
            cliente = operacion(form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, mensaje.format(cliente=cliente))
            return redirect("clientes:clientes")
    return None


@requiere_funcion("Clientes")
@require_http_methods(["GET", "POST"])
def nuevo(request):
    form = ClienteForm(request.POST or None)
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: crear_cliente(request.user, datos),
        "Se dio de alta «{cliente}».",
    )
    return respuesta or render(request, "clientes/cliente_form.html", {"form": form})


@requiere_funcion("Clientes")
@require_http_methods(["GET", "POST"])
def editar(request, pk):
    # Un cliente dado de baja no se edita: primero se reactiva (S-1).
    cliente = _buscar(cliente_editable, pk)
    form = ClienteForm(request.POST or None, initial=model_to_dict(cliente, CAMPOS_EDITABLES))
    respuesta = _guardar_con(
        request,
        form,
        lambda datos: modificar_cliente(request.user, cliente, datos),
        "Se guardaron los cambios de «{cliente}».",
    )
    if respuesta:
        return respuesta
    if request.method == "POST":
        # Si el servicio rechazó los datos, el título vuelve a mostrar lo guardado.
        cliente.refresh_from_db()
    return render(request, "clientes/cliente_form.html", {"form": form, "cliente": cliente})


@requiere_funcion("Clientes")
@require_http_methods(["GET", "POST"])
def baja(request, pk):
    """La confirmación avisa si el cliente debe: la deuda sigue y se puede cobrar (S-1)."""
    cliente = _buscar(cliente_editable, pk)
    if request.method == "POST":
        dar_de_baja(request.user, cliente)
        messages.success(request, f"Se dio de baja «{cliente}».")
        return redirect("clientes:clientes")
    return render(
        request, "clientes/cliente_baja.html", {"cliente": cliente, "saldo": saldo(cliente)}
    )


@requiere_funcion("Clientes")
@require_POST
def reactivar_cliente(request, pk):
    cliente = _buscar(cliente_dado_de_baja, pk)
    reactivar(request.user, cliente)
    messages.success(request, f"Se reactivó «{cliente}».")
    return redirect("clientes:clientes")


# SC-01: la cajera llega desde la venta y desde el cobro (DEC-116).
@requiere_funcion("Clientes", "Ventas", "Cobrar cuenta corriente")
@require_GET
def buscar(request):
    """Clientes para elegir, con saldo, límite, disponible y deuda vencida (SC-01)."""
    resultados, hay_mas = buscar_para_elegir(
        request.user, request.GET.get("q", ""), para_cobro=request.GET.get("para") == "cobro"
    )
    return JsonResponse({"resultados": resultados, "hay_mas": hay_mas})


# CU-04 Registrar pago de cliente (DEC-110, DEC-111, DEC-113; S-2, S-6, S-11)


def _cliente_inicial(request, form):
    """El cliente ya elegido: el del formulario que volvió con errores o el de `?cliente=`."""
    pk = form.data.get("cliente") if form.is_bound else request.GET.get("cliente", "")
    if not str(pk).isdecimal():
        return None
    return cliente_para_elegir(request.user, int(pk), para_cobro=True)


@requiere_funcion("Clientes", "Cobrar cuenta corriente")
@require_http_methods(["GET", "POST"])
def cobrar(request):
    """La cajera cobra en la caja abierta de hoy; el Administrador elige si entra a caja (S-6)."""
    es_admin = puede_gestionar(request.user)
    caja_del_dia = hay_caja_del_dia()
    form = CobroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        try:
            cobro = registrar_cobro(
                request.user,
                datos["cliente"],
                datos["monto"],
                datos["medio_pago"],
                # Sin caja de hoy, el del Administrador va sin movimiento de caja (DEC-110).
                entra_a_caja=not es_admin or (caja_del_dia and datos["entra_a_caja"]),
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request,
                f"Se registró el cobro N.º {cobro.pk} de {pesos(cobro.monto)} a {cobro.cliente}.",
            )
            if es_admin:
                return redirect("clientes:cobro", pk=cobro.pk)
            return redirect("clientes:cobrar")
    return render(
        request,
        "clientes/cobrar.html",
        {
            "form": form,
            "es_admin": es_admin,
            "caja_del_dia": caja_del_dia,
            "cliente_inicial": _cliente_inicial(request, form),
            "buscar_clientes": reverse("clientes:buscar"),
        },
    )


def _detalle_cobro(request, cobro, form, status=200):
    return render(
        request,
        "clientes/cobro_detalle.html",
        {
            "cobro": cobro,
            "ingreso": ingreso_de_cobro(cobro),
            "impedimento": impedimento_para_anular_cobro(cobro),
            "form": form,
        },
        status=status,
    )


@requiere_funcion("Clientes")
@require_GET
def cobro(request, pk):
    cobro = _buscar(lambda clave: cobro_con_detalles(request.user, clave), pk)
    return _detalle_cobro(request, cobro, AnularCobroForm())


@requiere_funcion("Clientes")
@require_POST
def cobro_anular(request, pk):
    """Con su caja abierta si entró a caja; si no, siempre (DEC-113)."""
    cobro = _buscar(lambda clave: cobro_con_detalles(request.user, clave), pk)
    form = AnularCobroForm(request.POST)
    if form.is_valid():
        try:
            anular_cobro(request.user, cobro, form.cleaned_data["motivo"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Se anuló el cobro N.º {cobro.pk}.")
            return redirect("clientes:cobro", pk=cobro.pk)
    cobro = _buscar(lambda clave: cobro_con_detalles(request.user, clave), pk)
    return _detalle_cobro(request, cobro, form, status=400)
