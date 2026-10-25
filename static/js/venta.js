// CU-01: lista de la venta en el navegador (DEC-47). Los montos que se ven acá son
// orientativos: el servidor vuelve a calcular todo al confirmar.
(function () {
  "use strict";

  const raiz = document.getElementById("venta");
  if (!raiz) return;

  const buscar = document.getElementById("buscar");
  const resultados = document.getElementById("resultados");
  const cuerpo = document.getElementById("lineas");
  const vacia = document.getElementById("vacia");
  const total = document.getElementById("total");
  const medio = document.getElementById("id_medio_pago");
  const errores = document.getElementById("errores");
  const confirmar = document.getElementById("confirmar");
  const csrf = raiz.querySelector("[name=csrfmiddlewaretoken]").value;
  const pesos = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // producto id -> { producto, cantidad (texto) }
  const lineas = new Map();

  function subtotal(linea) {
    const cantidad = Number(linea.cantidad.replace(",", "."));
    if (!(cantidad > 0)) return 0;
    // Mismo redondeo que el servidor (DEC-49), en centavos.
    return Math.round(cantidad * Number(linea.producto.precio) * 100) / 100;
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

  function dibujar(enfocar) {
    cuerpo.replaceChildren();
    for (const [id, linea] of lineas) {
      const porKg = linea.producto.unidad === "KG";
      const entrada = document.createElement("input");
      entrada.type = "number";
      entrada.min = porKg ? "0.001" : "1";
      entrada.step = porKg ? "0.001" : "1";
      entrada.value = linea.cantidad;
      entrada.className = "campo w-28";
      entrada.setAttribute("aria-label", `Cantidad de ${linea.producto.nombre}`);
      entrada.addEventListener("input", () => {
        linea.cantidad = entrada.value;
        dibujarTotales();
      });
      const etiqueta = document.createElement("span");
      etiqueta.className = "flex items-center gap-2";
      etiqueta.append(entrada, porKg ? "kg" : "u.");

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
        celda("px-5 py-3 font-medium", linea.producto.nombre),
        celda("px-5 py-3", etiqueta),
        celda("cifras px-5 py-3 text-right whitespace-nowrap", `$ ${pesos.format(Number(linea.producto.precio))}`),
        celda("cifras px-5 py-3 text-right whitespace-nowrap subtotal", ""),
        celda("px-5 py-3 text-right", quitar),
      );
      cuerpo.append(fila);
      if (enfocar === id) entrada.focus();
    }
    vacia.classList.toggle("hidden", lineas.size > 0);
    dibujarTotales();
  }

  function dibujarTotales() {
    let suma = 0;
    for (const fila of cuerpo.rows) {
      const linea = lineas.get(Number(fila.dataset.producto));
      const valor = subtotal(linea);
      suma += valor;
      fila.querySelector(".subtotal").textContent = `$ ${pesos.format(valor)}`;
    }
    total.textContent = `$ ${pesos.format(suma)}`;
  }

  // DEC-52 y DEC-53: por unidad suma 1 (o entra con 1); por kg deja el cursor en el peso.
  function agregar(producto) {
    const existente = lineas.get(producto.id);
    if (producto.unidad === "KG") {
      if (!existente) lineas.set(producto.id, { producto, cantidad: "" });
    } else if (existente) {
      existente.cantidad = String((Number(existente.cantidad) || 0) + 1);
    } else {
      lineas.set(producto.id, { producto, cantidad: "1" });
    }
    resultados.classList.add("hidden");
    buscar.value = "";
    mostrarErrores([]);
    dibujar(producto.unidad === "KG" ? producto.id : undefined);
    if (producto.unidad !== "KG") buscar.focus();
  }

  function mostrarResultados(lista) {
    resultados.replaceChildren();
    if (lista.length === 0) {
      const li = document.createElement("li");
      li.className = "px-3 py-2.5 text-sm text-gray-500";
      li.textContent = "No se encontraron productos.";
      resultados.append(li);
    }
    for (const producto of lista) {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "flex w-full items-center justify-between gap-4 px-3 py-2.5 text-left text-sm hover:bg-gray-50";
      const nombre = document.createElement("span");
      nombre.textContent = producto.plus ? `${producto.nombre} (${producto.plus})` : producto.nombre;
      const precio = document.createElement("span");
      precio.className = "cifras text-gray-600";
      precio.textContent = `$ ${pesos.format(Number(producto.precio))}${producto.unidad === "KG" ? " / kg" : ""}`;
      boton.append(nombre, precio);
      boton.addEventListener("click", () => agregar(producto));
      const li = document.createElement("li");
      li.append(boton);
      resultados.append(li);
    }
    resultados.classList.remove("hidden");
  }

  async function consultar(texto) {
    const respuesta = await fetch(`${raiz.dataset.buscar}?q=${encodeURIComponent(texto)}`, {
      headers: { Accept: "application/json" },
    });
    return respuesta.json();
  }

  buscar.addEventListener("keydown", async (evento) => {
    if (evento.key !== "Enter") return;
    evento.preventDefault();
    const texto = buscar.value.trim();
    if (!texto) return;
    const datos = await consultar(texto);
    if (datos.exacto) agregar(datos.exacto);
    else mostrarResultados(datos.resultados);
  });

  document.getElementById("cancelar").addEventListener("click", () => {
    // A5: no se registra nada.
    lineas.clear();
    medio.value = "";
    resultados.classList.add("hidden");
    mostrarErrores([]);
    dibujar();
    buscar.focus();
  });

  confirmar.addEventListener("click", async () => {
    const lista = [...lineas.values()].map((l) => ({
      producto: l.producto.id,
      cantidad: l.cantidad.replace(",", "."),
    }));
    const cuerpoPedido = new URLSearchParams({
      csrfmiddlewaretoken: csrf,
      medio_pago: medio.value,
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
      if (datos.ticket) {
        window.location.assign(datos.ticket);
        return;
      }
      mostrarErrores(datos.errores || ["No se pudo registrar la venta."]);
    } catch {
      mostrarErrores(["No se pudo registrar la venta. Revisá la conexión e intentá de nuevo."]);
    }
    confirmar.disabled = false;
  });

  dibujar();
})();
