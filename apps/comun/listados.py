from django.core.paginator import Paginator

# DEC-95: los listados paginan de a 25.
POR_PAGINA = 25


def filtrar_y_paginar(request, form, listar):
    """Listado con filtro (DEC-145, DEC-152, DEC-155): un filtro inválido muestra el error y no
    lista. `listar` recibe los datos válidos del filtro y devuelve el queryset.

    Devuelve la página y los filtros de la dirección sin la página, para conservarlos al
    paginar.
    """
    datos = form.cleaned_data if form.is_valid() else {}
    lista = listar(datos)
    if form.is_bound and not form.is_valid():
        lista = lista.none()
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return pagina, filtros.urlencode()
