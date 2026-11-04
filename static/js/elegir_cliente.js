// SC-01 en pantalla (DEC-116, DEC-118): buscador de clientes para la venta (SC-03) y el cobro
// (CU-04). Se comporta como el buscador de productos de la venta (DEC-97): filtra al dejar de
// escribir y se recorre con flechas, Inicio, Fin, Enter y Escape. Reutiliza la lógica de
// buscador.js (`crearBuscadorDiferido`, `moverSeleccion`), que hay que cargar antes.
(function (raiz) {
  "use strict";

  // `para` es "" en la venta (solo activos) y "cobro" en el cobro (suma los dados de baja que
  // deben). Devuelve { resultados, hay_mas } de /clientes/buscar/.
  async function consultarClientes(url, texto, para = "") {
    const parametros = new URLSearchParams({ q: texto });
    if (para) parametros.set("para", para);
    const respuesta = await fetch(`${url}?${parametros}`, { headers: { Accept: "application/json" } });
    return respuesta.json();
  }

  function crearElegirCliente({ entrada, lista, url, para = "", alElegir }) {
    const buscador = raiz.crearBuscadorDiferido();
    let visibles = [];
    let marcado = -1;

    entrada.setAttribute("role", "combobox");
    entrada.setAttribute("aria-expanded", "false");
    entrada.setAttribute("aria-autocomplete", "list");
    entrada.setAttribute("aria-controls", lista.id);
    lista.setAttribute("role", "listbox");

    function marcar(indice) {
      const opciones = lista.querySelectorAll("[role=option]");
      marcado = indice;
      opciones.forEach((opcion, i) => {
        opcion.setAttribute("aria-selected", String(i === marcado));
        opcion.classList.toggle("bg-gray-100", i === marcado);
      });
      if (marcado >= 0) {
        entrada.setAttribute("aria-activedescendant", opciones[marcado].id);
        opciones[marcado].scrollIntoView({ block: "nearest" });
      } else {
        entrada.removeAttribute("aria-activedescendant");
      }
    }

    function cerrar() {
      buscador.descartar();
      lista.classList.add("hidden");
      entrada.setAttribute("aria-expanded", "false");
      visibles = [];
      marcar(-1);
    }

    function aviso(texto) {
      const li = document.createElement("li");
      li.className = "px-3 py-2 text-sm text-gray-500";
      li.textContent = texto;
      return li;
    }

    function elegir(cliente) {
      cerrar();
      entrada.value = "";
      alElegir(cliente);
    }

    function mostrar(clientes, hayMas) {
      lista.replaceChildren();
      visibles = clientes;
      if (clientes.length === 0) lista.append(aviso("No hay clientes que coincidan."));
      clientes.forEach((cliente, i) => {
        const opcion = document.createElement("li");
        opcion.id = `${lista.id}-${cliente.id}`;
        opcion.setAttribute("role", "option");
        opcion.className = "flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm hover:bg-gray-50";
        const nombre = document.createElement("span");
        nombre.className = "font-medium";
        nombre.textContent = cliente.nombre;
        if (!cliente.activo) {
          const baja = document.createElement("span");
          baja.className = "ml-2 rounded-full bg-gray-200 px-2 py-0.5 text-[11px] font-medium text-gray-600";
          baja.textContent = "Dado de baja";
          nombre.append(baja);
        }
        const telefono = document.createElement("span");
        telefono.className = "cifras whitespace-nowrap text-gray-500";
        telefono.textContent = cliente.telefono;
        opcion.append(nombre, telefono);
        // mousedown evita que el clic saque el foco del buscador antes de elegir.
        opcion.addEventListener("mousedown", (evento) => evento.preventDefault());
        opcion.addEventListener("click", () => elegir(cliente));
        opcion.addEventListener("mousemove", () => marcado !== i && marcar(i));
        lista.append(opcion);
      });
      if (hayMas) lista.append(aviso("Seguí escribiendo para ver más."));
      lista.classList.remove("hidden");
      entrada.setAttribute("aria-expanded", "true");
      marcar(-1);
    }

    async function filtrar(texto, turno) {
      const datos = await consultarClientes(url, texto, para);
      if (buscador.vigente(turno)) mostrar(datos.resultados, datos.hay_mas);
    }

    entrada.addEventListener("input", () => {
      marcar(-1);
      const texto = entrada.value.trim();
      if (!texto) {
        cerrar();
        return;
      }
      buscador.diferir(texto, filtrar);
    });

    entrada.addEventListener("keydown", (evento) => {
      const abierta = !lista.classList.contains("hidden");
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(evento.key) && (abierta || evento.key === "ArrowDown")) {
        evento.preventDefault();
        if (abierta) marcar(raiz.moverSeleccion(marcado, visibles.length, evento.key));
        else if (entrada.value.trim()) filtrar(entrada.value.trim(), buscador.inmediato());
        return;
      }
      if (evento.key === "Escape" && abierta) {
        evento.preventDefault();
        cerrar();
        return;
      }
      if (evento.key !== "Enter") return;
      evento.preventDefault();
      // El marcado con las flechas; si la lista tiene uno solo, ese.
      if (abierta && marcado >= 0) elegir(visibles[marcado]);
      else if (abierta && visibles.length === 1) elegir(visibles[0]);
      else if (entrada.value.trim()) filtrar(entrada.value.trim(), buscador.inmediato());
    });

    document.addEventListener("click", (evento) => {
      if (![entrada, lista].some((parte) => parte.contains(evento.target))) cerrar();
    });

    return { cerrar };
  }

  const exportado = { crearElegirCliente, consultarClientes };
  if (typeof module !== "undefined" && module.exports) module.exports = exportado;
  else Object.assign(raiz, exportado);
})(typeof window !== "undefined" ? window : globalThis);
