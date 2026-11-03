// CU-05: ingreso de mercadería a crédito o al contado. La lista vive en el navegador; el servidor valida
// y calcula todo al confirmar (DEC-79, DEC-89). El precio se completa con el último precio
// de compra del proveedor (DEC-90) y se puede cambiar.
(function () {
  "use strict";

  const raiz = document.getElementById("ingreso");
  if (!raiz) return;

  const proveedor = document.getElementById("id_proveedor");
  const observacion = document.getElementById("id_observacion");
  const condicion = document.getElementById("id_condicion_pago");
  const medio = document.getElementById("id_medio_pago");
  const bloqueMedio = document.getElementById("bloque-medio");
  const tituloTotal = document.getElementById("titulo-total");
  const buscar = document.getElementById("buscar");
  const resultados = document.getElementById("resultados");
  const cuerpo = document.getElementById("lineas");
  const vacia = document.getElementById("vacia");
  const total = document.getElementById("total");
  const errores = document.getElementById("errores");
  const confirmar = document.getElementById("confirmar");
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;
  const pesos = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // producto id -> { producto, cantidad (texto), precio (texto), precioEditado }
  const lineas = new Map();
  let confirmado = false;

  function numero(texto) {
    return Number(String(texto).replace(",", "."));
  }

  function subtotal(linea) {
    const cantidad = numero(linea.cantidad);
    const precio = numero(linea.precio);
    if (!(cantidad > 0) || !(precio >= 0)) return 0;
    // Mismo redondeo que el servidor (DEC-89, DEC-49), en centavos.
    return Math.round(cantidad * precio * 100) / 100;
  }

  function mostrarErrores(lista) {
    errores.replaceChildren(...lista.map((texto) => {
      const p = document.createElement("p");
      p.textContent = texto;
      return p;
    }));
    errores.classList.toggle("hidden", lista.length === 0);
  }

  function celda(clase, contenido) {
    const td = document.createElement("td");
    td.className = clase;
    if (contenido instanceof Node) td.append(contenido);
    else td.textContent = contenido;
    return td;
  }

  function entrada(valor, paso, etiqueta, alCambiar) {
    const campo = document.createElement("input");
    campo.type = "number";
    campo.min = "0";
    campo.step = paso;
    campo.value = valor;
    campo.className = "campo w-32";
    campo.setAttribute("aria-label", etiqueta);
    campo.addEventListener("input", () => alCambiar(campo.value));
    campo.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter") {
        evento.preventDefault();
        buscar.focus();
      }
    });
    return campo;
  }

  function dibujar(enfocar) {
    cuerpo.replaceChildren();
    for (const [id, linea] of lineas) {
      const porKg = linea.producto.unidad === "KG";
      const cantidad = entrada(linea.cantidad, porKg ? "0.001" : "1", `Cantidad de ${linea.producto.nombre}`, (valor) => {
        linea.cantidad = valor;
        dibujarTotales();
      });
      const precio = entrada(linea.precio, "0.01", `Precio de compra de ${linea.producto.nombre}`, (valor) => {
        linea.precio = valor;
        linea.precioEditado = true;
        dibujarTotales();
      });
      const conUnidad = document.createElement("span");
      conUnidad.className = "flex items-center gap-2";
      conUnidad.append(cantidad, porKg ? "kg" : "u.");
      const nombre = document.createElement("span");
      nombre.className = "font-medium";
      nombre.textContent = linea.producto.nombre;
      const nombreCelda = document.createElement("span");
      nombreCelda.append(nombre);
      if (!linea.producto.controla_stock) {
        // DEC-94: suma a la deuda, el stock no cambia.
        const nota = document.createElement("span");
        nota.className = "block text-xs text-gray-500";
        nota.textContent = "Sin control de stock";
        nombreCelda.append(nota);
      }
      const quitar = document.createElement("button");
      quitar.type = "button";
      quitar.textContent = "Quitar";
      quitar.className = "rounded-md px-2.5 py-1.5 font-medium text-red-700 hover:bg-red-50";
      quitar.addEventListener("click", () => {
        lineas.delete(id);
        dibujar();
        buscar.focus();
      });
      const fila = document.createElement("tr");
      fila.dataset.producto = id;
      fila.append(
        celda("px-5 py-3", nombreCelda),
        celda("px-5 py-3", conUnidad),
        celda("px-5 py-3", precio),
        celda("cifras px-5 py-3 text-right whitespace-nowrap subtotal", ""),
        celda("px-5 py-3 text-right", quitar),
      );
      cuerpo.append(fila);
      if (enfocar === id) cantidad.focus();
    }
    vacia.classList.toggle("hidden", lineas.size > 0);
    dibujarTotales();
  }

  function dibujarTotales() {
    let suma = 0;
    for (const fila of cuerpo.rows) {
      const valor = subtotal(lineas.get(Number(fila.dataset.producto)));
      suma += valor;
      fila.querySelector(".subtotal").textContent = `$ ${pesos.format(valor)}`;
    }
    total.textContent = `$ ${pesos.format(Math.round(suma * 100) / 100)}`;
  }

  function agregar(producto) {
    cerrarLista();
    buscar.value = "";
    mostrarErrores([]);
    // Una línea por producto: si ya está, se corrige su cantidad.
    if (!lineas.has(producto.id)) {
      lineas.set(producto.id, { producto, cantidad: "", precio: producto.precio, precioEditado: false });
    }
    dibujar(producto.id);
  }

  // Búsqueda: filtra al dejar de escribir (como la venta, DEC-97).
  const buscador = crearBuscadorDiferido();
  let visibles = [];
  let marcado = -1;

  function marcar(indice) {
    const opciones = resultados.querySelectorAll("[role=option]");
    marcado = indice;
    opciones.forEach((opcion, i) => {
      opcion.setAttribute("aria-selected", String(i === marcado));
      opcion.classList.toggle("bg-gray-100", i === marcado);
    });
    if (marcado >= 0) {
      buscar.setAttribute("aria-activedescendant", opciones[marcado].id);
      opciones[marcado].scrollIntoView({ block: "nearest" });
    } else {
      buscar.removeAttribute("aria-activedescendant");
    }
  }

  function cerrarLista() {
    buscador.descartar();
    resultados.classList.add("hidden");
    buscar.setAttribute("aria-expanded", "false");
    visibles = [];
    marcar(-1);
  }

  function aviso(texto) {
    const li = document.createElement("li");
    li.className = "px-3 py-2.5 text-sm text-gray-500";
    li.textContent = texto;
    return li;
  }

  function mostrarResultados(lista, hayMas) {
    resultados.replaceChildren();
    visibles = lista;
    if (lista.length === 0) resultados.append(aviso("No se encontraron productos. Podés crearlo con «Crear producto»."));
    lista.forEach((producto, i) => {
      const opcion = document.createElement("li");
      opcion.id = `producto-${producto.id}`;
      opcion.setAttribute("role", "option");
      opcion.className = "flex cursor-pointer items-center justify-between gap-4 px-3 py-2.5 text-sm hover:bg-gray-50";
      const nombre = document.createElement("span");
      nombre.textContent = producto.plus ? `${producto.nombre} (${producto.plus})` : producto.nombre;
      const precio = document.createElement("span");
      precio.className = "cifras whitespace-nowrap text-gray-600";
      const unidad = producto.unidad === "KG" ? "/ kg" : "/ u.";
      precio.textContent = producto.precio ? `Último: $ ${pesos.format(Number(producto.precio))} ${unidad}` : "Sin precio anterior";
      opcion.append(nombre, precio);
      opcion.addEventListener("mousedown", (evento) => evento.preventDefault());
      opcion.addEventListener("click", () => agregar(producto));
      resultados.append(opcion);
    });
    if (hayMas) resultados.append(aviso("Seguí escribiendo para ver más."));
    resultados.classList.remove("hidden");
    buscar.setAttribute("aria-expanded", "true");
    marcar(-1);
  }

  async function filtrar(texto, turno) {
    const url = `${raiz.dataset.buscar}?q=${encodeURIComponent(texto)}&proveedor=${encodeURIComponent(proveedor.value)}`;
    const datos = await (await fetch(url, { headers: { Accept: "application/json" } })).json();
    if (buscador.vigente(turno)) mostrarResultados(datos.resultados, datos.hay_mas);
  }

  buscar.addEventListener("input", () => {
    marcar(-1);
    if (buscar.value.trim()) buscador.diferir(buscar.value.trim(), filtrar);
    else cerrarLista();
  });
  buscar.addEventListener("keydown", (evento) => {
    const abierta = !resultados.classList.contains("hidden");
    if (abierta && ["ArrowDown", "ArrowUp", "Home", "End"].includes(evento.key)) {
      evento.preventDefault();
      marcar(moverSeleccion(marcado, visibles.length, evento.key));
    } else if (evento.key === "Escape" && abierta) {
      evento.preventDefault();
      cerrarLista();
    } else if (evento.key === "Enter") {
      evento.preventDefault();
      if (abierta && marcado >= 0) agregar(visibles[marcado]);
      else if (buscar.value.trim()) filtrar(buscar.value.trim(), buscador.inmediato());
    }
  });
  document.addEventListener("click", (evento) => {
    if (!buscar.contains(evento.target) && !resultados.contains(evento.target)) cerrarLista();
  });

  // DEC-90: al cambiar de proveedor, los precios que no se tocaron se completan otra vez.
  proveedor.addEventListener("change", async () => {
    const sinTocar = [...lineas.values()].filter((l) => !l.precioEditado);
    if (sinTocar.length === 0 || !proveedor.value) return;
    const ids = sinTocar.map((l) => l.producto.id).join(",");
    const url = `${raiz.dataset.buscar}?proveedor=${encodeURIComponent(proveedor.value)}&ids=${ids}`;
    const { precios } = await (await fetch(url, { headers: { Accept: "application/json" } })).json();
    for (const linea of sinTocar) linea.precio = precios[linea.producto.id] || "";
    dibujar();
  });

  // CU-05 A1: alta de producto en un diálogo, sin perder el ingreso (DEC-91).
  const alta = document.getElementById("alta-producto");
  const formAlta = document.getElementById("form-producto");
  const guardar = document.getElementById("alta-guardar");

  function erroresDelAlta(porCampo) {
    for (const lugar of formAlta.querySelectorAll("[data-error-de]")) {
      const lista = porCampo[lugar.dataset.errorDe] || [];
      lugar.textContent = lista.join(" ");
      lugar.classList.toggle("hidden", lista.length === 0);
    }
  }

  document.getElementById("crear-producto").addEventListener("click", () => {
    const texto = buscar.value.trim();
    formAlta.reset();
    erroresDelAlta({});
    // Como DEC-64: solo dígitos es un código; si no, es el nombre.
    if (texto) formAlta.elements[/^\d+$/.test(texto) ? "producto-plus_interno" : "producto-nombre"].value = texto;
    cerrarLista();
    alta.showModal();
    formAlta.elements["producto-nombre"].focus();
  });
  document.getElementById("alta-cancelar").addEventListener("click", () => {
    alta.close();
    buscar.focus();
  });
  formAlta.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const datos = new FormData(formAlta);
    datos.append("csrfmiddlewaretoken", csrf);
    guardar.disabled = true;
    try {
      const respuesta = await fetch(raiz.dataset.producto, {
        method: "POST",
        body: datos,
        headers: { "X-CSRFToken": csrf, Accept: "application/json" },
      });
      const resultado = await respuesta.json();
      if (resultado.producto) {
        alta.close();
        agregar(resultado.producto);
      } else {
        erroresDelAlta(resultado.errores || { __all__: ["No se pudo dar de alta el producto."] });
      }
    } catch {
      erroresDelAlta({ __all__: ["No se pudo dar de alta el producto. Revisá la conexión e intentá de nuevo."] });
    }
    guardar.disabled = false;
  });

  // DEC-81: al contado se elige el medio y el total se paga en la misma operación.
  function mostrarCondicion() {
    const contado = condicion.value === "CONTADO";
    bloqueMedio.classList.toggle("hidden", !contado);
    tituloTotal.textContent = contado ? "Total (se paga ahora)" : "Total (deuda)";
  }
  condicion.addEventListener("change", mostrarCondicion);
  mostrarCondicion();

  window.addEventListener("beforeunload", (evento) => {
    if (lineas.size === 0 || confirmado) return;
    evento.preventDefault();
    evento.returnValue = "";
  });

  confirmar.addEventListener("click", async () => {
    const lista = [...lineas.values()].map((l) => ({
      producto: l.producto.id,
      cantidad: String(l.cantidad).replace(",", "."),
      precio: String(l.precio).replace(",", "."),
    }));
    const cuerpoPedido = new URLSearchParams({
      csrfmiddlewaretoken: csrf,
      proveedor: proveedor.value,
      observacion: observacion.value,
      condicion_pago: condicion.value,
      medio_pago: condicion.value === "CONTADO" ? medio.value : "",
      sale_de_caja: document.getElementById("id_sale_de_caja").checked ? "on" : "",
      lineas: JSON.stringify(lista),
    });
    confirmar.disabled = true;
    try {
      const respuesta = await fetch(raiz.dataset.confirmar, {
        method: "POST",
        body: cuerpoPedido,
        headers: { "X-CSRFToken": csrf, Accept: "application/json" },
      });
      const datos = await respuesta.json();
      if (datos.detalle) {
        confirmado = true;
        window.location.assign(datos.detalle);
        return;
      }
      mostrarErrores(datos.errores || ["No se pudo registrar el ingreso."]);
    } catch {
      mostrarErrores(["No se pudo registrar el ingreso. Revisá la conexión e intentá de nuevo."]);
    }
    confirmar.disabled = false;
  });

  dibujar();
})();
