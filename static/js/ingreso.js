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
    campo.className = "campo w-28";
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
      nombre.className = "font-semibold";
      nombre.textContent = linea.producto.nombre;
      const nombreCelda = document.createElement("span");
      nombreCelda.append(nombre);
      if (!linea.producto.controla_stock) {
        // DEC-94: suma a la deuda, el stock no cambia.
        const nota = document.createElement("span");
        nota.className = "block text-xs text-tinta-suave";
        nota.textContent = "Sin control de stock";
        nombreCelda.append(nota);
      }
      const quitar = document.createElement("button");
      quitar.type = "button";
      quitar.textContent = "Quitar";
      quitar.className = "boton-discreto-peligro";
      quitar.addEventListener("click", () => {
        lineas.delete(id);
        dibujar();
        buscar.focus();
      });
      const fila = document.createElement("tr");
      fila.dataset.producto = id;
      fila.append(
        celda("", nombreCelda),
        celda("", conUnidad),
        celda("", precio),
        celda("monto text-right whitespace-nowrap subtotal", ""),
        celda("text-right", quitar),
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

  // Búsqueda: filtra al dejar de escribir (como la venta, DEC-97). Buscador común con la venta
  // (L13, DEC-181): en el ingreso, Enter filtra sin agregar el código exacto y la lista no se
  // abre sin texto.
  const buscador = crearBuscadorProductos({
    entrada: buscar,
    lista: resultados,
    async consultar(texto) {
      const url = `${raiz.dataset.buscar}?q=${encodeURIComponent(texto)}&proveedor=${encodeURIComponent(proveedor.value)}`;
      return (await fetch(url, { headers: { Accept: "application/json" } })).json();
    },
    detalle(producto) {
      const unidad = producto.unidad === "KG" ? "/ kg" : "/ u.";
      return producto.precio ? `Último: $ ${pesos.format(Number(producto.precio))} ${unidad}` : "Sin precio anterior";
    },
    sinResultados: () => {
      const li = document.createElement("li");
      li.className = "opcion-vacia";
      li.textContent = "No se encontraron productos. Podés crearlo con «Crear producto».";
      return li;
    },
    alElegir: (producto) => agregar(producto),
  });
  const cerrarLista = buscador.cerrar;

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
