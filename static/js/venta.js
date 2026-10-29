// CU-01: lista de la venta en el navegador (DEC-47). Los montos que se ven acá son
// orientativos: el servidor vuelve a calcular todo al confirmar.
(function () {
  "use strict";

  const raiz = document.getElementById("venta");
  if (!raiz) return;

  const buscar = document.getElementById("buscar");
  const resultados = document.getElementById("resultados");
  const verProductos = document.getElementById("ver-productos");
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

  // La venta en curso se guarda en la pestaña, por usuario, hasta confirmarla o vaciarla.
  let almacen = null;
  try {
    almacen = window.sessionStorage;
  } catch {
    // Sin almacenamiento: la venta no se guarda.
  }
  const guardada = almacen
    ? crearVentaGuardada(almacen, `venta-en-curso-${raiz.dataset.usuario}`)
    : { guardar() {}, leer: () => null, borrar() {} };

  function persistir() {
    guardada.guardar([...lineas.values()].map(({ producto, cantidad }) => ({ producto, cantidad })), medio.value);
  }

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
      // DEC-75: Enter vuelve al buscador; una lectura del lector acá no se suma a la cantidad,
      // se busca como producto (DF-01).
      const detector = crearDetectorLector();
      entrada.addEventListener("keydown", (evento) => {
        if (evento.key === "Enter") {
          evento.preventDefault();
          const lectura = detector.enter(evento.timeStamp);
          if (lectura) {
            entrada.value = lectura.valorPrevio;
            linea.cantidad = lectura.valorPrevio;
            dibujarTotales();
            buscarTexto(lectura.texto);
          } else {
            buscar.focus();
          }
        } else if (evento.key.length === 1 && !evento.ctrlKey && !evento.metaKey && !evento.altKey) {
          detector.tecla(evento.key, evento.timeStamp, entrada.value);
        }
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
    persistir();
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
    cerrarLista();
    buscar.value = "";
    mostrarErrores([]);
    dibujar(producto.unidad === "KG" ? producto.id : undefined);
    if (producto.unidad !== "KG") buscar.focus();
  }

  // DEC-97: lista para elegir, navegable con flechas; el foco queda en el buscador.
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
    li.className = "flex items-center justify-between gap-4 px-3 py-2.5 text-sm text-gray-500";
    li.textContent = texto;
    return li;
  }

  function mostrarResultados(lista, texto, hayMas) {
    resultados.replaceChildren();
    visibles = lista;
    if (lista.length === 0) {
      const li = aviso("No se encontraron productos.");
      // A1: solo con permiso de alta (DEC-63).
      if (alta) {
        const crear = document.createElement("button");
        crear.type = "button";
        crear.textContent = "Crear producto";
        crear.className = "rounded-md border border-gray-300 px-3 py-1.5 font-medium text-gray-800 hover:bg-gray-50";
        crear.addEventListener("click", () => abrirAlta(texto));
        li.append(crear);
      }
      resultados.append(li);
    }
    lista.forEach((producto, i) => {
      const opcion = document.createElement("li");
      opcion.id = `producto-${producto.id}`;
      opcion.setAttribute("role", "option");
      opcion.className = "flex cursor-pointer items-center justify-between gap-4 px-3 py-2.5 text-sm hover:bg-gray-50";
      const nombre = document.createElement("span");
      nombre.textContent = producto.plus ? `${producto.nombre} (${producto.plus})` : producto.nombre;
      const precio = document.createElement("span");
      precio.className = "cifras whitespace-nowrap text-gray-600";
      precio.textContent = `$ ${pesos.format(Number(producto.precio))} ${producto.unidad === "KG" ? "/ kg" : "/ u."}`;
      opcion.append(nombre, precio);
      // mousedown evita que el clic saque el foco del buscador antes de agregar.
      opcion.addEventListener("mousedown", (evento) => evento.preventDefault());
      opcion.addEventListener("click", () => agregar(producto));
      opcion.addEventListener("mousemove", () => marcado !== i && marcar(i));
      resultados.append(opcion);
    });
    if (hayMas) resultados.append(aviso("Seguí escribiendo para ver más."));
    resultados.classList.remove("hidden");
    buscar.setAttribute("aria-expanded", "true");
    marcar(-1);
  }

  async function consultar(texto) {
    const respuesta = await fetch(`${raiz.dataset.buscar}?q=${encodeURIComponent(texto)}`, {
      headers: { Accept: "application/json" },
    });
    return respuesta.json();
  }

  async function buscarTexto(texto) {
    const turno = buscador.inmediato();
    const datos = await consultar(texto);
    if (!buscador.vigente(turno)) return;
    if (datos.exacto) agregar(datos.exacto);
    else {
      buscar.value = texto;
      mostrarResultados(datos.resultados, texto, datos.hay_mas);
      buscar.focus();
    }
  }

  async function filtrar(texto, turno) {
    const datos = await consultar(texto);
    if (buscador.vigente(turno)) mostrarResultados(datos.resultados, texto, datos.hay_mas);
  }

  function abrirLista() {
    filtrar(buscar.value.trim(), buscador.inmediato());
  }

  // DEC-97: la lista se abre a pedido (clic en el buscador vacío, flecha abajo o el botón),
  // nunca sola al volver el foco después de agregar un producto.
  buscar.addEventListener("click", () => {
    if (!buscar.value.trim()) abrirLista();
  });
  verProductos.addEventListener("click", () => {
    abrirLista();
    buscar.focus();
  });
  buscar.addEventListener("input", () => {
    marcar(-1);
    buscador.diferir(buscar.value.trim(), filtrar);
  });
  document.addEventListener("click", (evento) => {
    if (![buscar, resultados, verProductos].some((parte) => parte.contains(evento.target))) cerrarLista();
  });

  buscar.addEventListener("keydown", (evento) => {
    const abierta = !resultados.classList.contains("hidden");
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(evento.key) && (abierta || evento.key === "ArrowDown")) {
      evento.preventDefault();
      if (abierta) marcar(moverSeleccion(marcado, visibles.length, evento.key));
      else abrirLista();
      return;
    }
    if (evento.key === "Escape" && abierta) {
      evento.preventDefault();
      cerrarLista();
      return;
    }
    if (evento.key !== "Enter") return;
    evento.preventDefault();
    // Un producto marcado con las flechas; si no, el plus exacto o la búsqueda (DEC-52).
    if (abierta && marcado >= 0) {
      agregar(visibles[marcado]);
      return;
    }
    const texto = buscar.value.trim();
    if (texto) buscarTexto(texto);
  });

  // CU-01 A1: alta de producto en un diálogo, sin perder la venta en curso (DEC-62).
  const alta = raiz.dataset.producto ? document.getElementById("alta-producto") : null;
  let abrirAlta;
  if (alta) {
    const formAlta = document.getElementById("form-producto");
    const guardar = document.getElementById("alta-guardar");

    function erroresDelAlta(porCampo) {
      for (const lugar of formAlta.querySelectorAll("[data-error-de]")) {
        const lista = porCampo[lugar.dataset.errorDe] || [];
        lugar.textContent = lista.join(" ");
        lugar.classList.toggle("hidden", lista.length === 0);
      }
    }

    abrirAlta = (texto) => {
      formAlta.reset();
      erroresDelAlta({});
      // DEC-64: solo dígitos es un código del lector; si no, es el nombre.
      const campo = /^\d+$/.test(texto) ? "plus_interno" : "nombre";
      formAlta.elements[`producto-${campo}`].value = texto;
      alta.showModal();
      formAlta.elements[campo === "nombre" ? "producto-categoria" : "producto-nombre"].focus();
    };

    document.getElementById("alta-cancelar").addEventListener("click", () => {
      alta.close();
      buscar.focus();
    });

    formAlta.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const cuerpoPedido = new FormData(formAlta);
      cuerpoPedido.append("csrfmiddlewaretoken", csrf);
      guardar.disabled = true;
      try {
        const respuesta = await fetch(raiz.dataset.producto, {
          method: "POST",
          body: cuerpoPedido,
          headers: { "X-CSRFToken": csrf, Accept: "application/json" },
        });
        const datos = await respuesta.json();
        if (datos.producto) {
          alta.close();
          agregar(datos.producto); // DEC-65
        } else {
          erroresDelAlta(datos.errores || { __all__: ["No se pudo dar de alta el producto."] });
        }
      } catch {
        erroresDelAlta({ __all__: ["No se pudo dar de alta el producto. Revisá la conexión e intentá de nuevo."] });
      }
      guardar.disabled = false;
    });
  }

  medio.addEventListener("change", persistir);

  // Avisa antes de salir de la pantalla con productos cargados.
  window.addEventListener("beforeunload", (evento) => {
    if (lineas.size === 0) return;
    evento.preventDefault();
    evento.returnValue = "";
  });

  document.getElementById("cancelar").addEventListener("click", () => {
    // A5: no se registra nada.
    lineas.clear();
    guardada.borrar();
    medio.value = "";
    cerrarLista();
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
        lineas.clear();
        guardada.borrar();
        window.location.assign(datos.ticket);
        return;
      }
      mostrarErrores(datos.errores || ["No se pudo registrar la venta."]);
    } catch {
      mostrarErrores(["No se pudo registrar la venta. Revisá la conexión e intentá de nuevo."]);
    }
    confirmar.disabled = false;
  });

  const previa = guardada.leer();
  if (previa) {
    for (const linea of previa.lineas) lineas.set(linea.producto.id, linea);
    if ([...medio.options].some((opcion) => opcion.value === previa.medio)) medio.value = previa.medio;
  }
  dibujar();
})();
