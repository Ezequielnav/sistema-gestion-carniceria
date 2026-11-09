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
  // DEC-173: tope de líneas (una por producto), el mismo que valida el servidor.
  const lineasMaximas = Number(raiz.dataset.lineasMaximas) || Infinity;
  const pesos = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // producto id -> { producto, cantidad (texto) }
  const lineas = new Map();
  // SC-03 (DEC-123): el cliente elegido con SC-01 cuando el medio es cuenta corriente.
  let cliente = null;
  let totalActual = 0;

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
    guardada.guardar(
      [...lineas.values()].map(({ producto, cantidad }) => ({ producto, cantidad })),
      medio.value,
      cliente,
    );
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

  function nombreConAviso(nombre) {
    const contenido = document.createElement("span");
    const aviso = document.createElement("span");
    aviso.className = "aviso-stock mt-1 block hidden text-xs font-normal text-amber-800";
    aviso.setAttribute("role", "status");
    contenido.append(nombre, aviso);
    return contenido;
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
        celda("px-5 py-3 font-medium", nombreConAviso(linea.producto.nombre)),
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
      // DEC-102: avisa con la cantidad disponible, sin bloquear (DEC-46).
      const aviso = fila.querySelector(".aviso-stock");
      aviso.textContent = avisoDeStock(linea.producto, linea.cantidad) || "";
      aviso.classList.toggle("hidden", !aviso.textContent);
    }
    total.textContent = `$ ${pesos.format(suma)}`;
    totalActual = suma;
    cuentaCorriente.dibujar();
    persistir();
  }

  // DEC-52 y DEC-53: por unidad suma 1 (o entra con 1); por kg deja el cursor en el peso.
  function agregar(producto) {
    const existente = lineas.get(producto.id);
    if (!existente && lineas.size >= lineasMaximas) {
      // Sumar a una línea existente sigue funcionando; una nueva, no (DEC-173).
      cerrarLista();
      buscar.value = "";
      mostrarErrores([raiz.dataset.mensajeLineasMaximas]);
      buscar.focus();
      return;
    }
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

  // DEC-97: lista para elegir, navegable con flechas; el foco queda en el buscador. Buscador
  // común con el ingreso (L13, DEC-181), con las opciones propias de la venta.
  const buscador = crearBuscadorProductos({
    entrada: buscar,
    lista: resultados,
    boton: verProductos,
    async consultar(texto) {
      const respuesta = await fetch(`${raiz.dataset.buscar}?q=${encodeURIComponent(texto)}`, {
        headers: { Accept: "application/json" },
      });
      return respuesta.json();
    },
    detalle: (producto) =>
      `$ ${pesos.format(Number(producto.precio))} ${producto.unidad === "KG" ? "/ kg" : "/ u."}`,
    sinResultados(texto) {
      const li = document.createElement("li");
      li.className = "flex items-center justify-between gap-4 px-3 py-2.5 text-sm text-gray-500";
      li.textContent = "No se encontraron productos.";
      // A1: solo con permiso de alta (DEC-63).
      if (alta) {
        const crear = document.createElement("button");
        crear.type = "button";
        crear.textContent = "Crear producto";
        crear.className = "rounded-md border border-gray-300 px-3 py-1.5 font-medium text-gray-800 hover:bg-gray-50";
        crear.addEventListener("click", () => abrirAlta(texto));
        li.append(crear);
      }
      return li;
    },
    alElegir: (producto) => agregar(producto),
    exactoConEnter: true,
    abrirSinTexto: true,
    marcarConMouse: true,
  });
  const cerrarLista = buscador.cerrar;
  const buscarTexto = buscador.buscarTexto;

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

  // SC-03: con el medio cuenta corriente se elige el cliente (SC-01). El servidor vuelve a
  // validar cliente, límite y saldo al confirmar (DEC-47, DEC-108).
  const cuentaCorriente = (function () {
    const bloque = document.getElementById("cuenta-corriente");
    if (!bloque) return { dibujar() {}, mostrar() {}, refrescar() {}, activo: () => false };
    const elegir = document.getElementById("elegir-cliente");
    const buscarCliente = document.getElementById("buscar-cliente");
    const lista = document.getElementById("clientes");
    const elegido = document.getElementById("cliente-elegido");
    const campos = {
      nombre: document.getElementById("cliente-nombre"),
      saldo: document.getElementById("cliente-saldo"),
      limite: document.getElementById("cliente-limite"),
      disponible: document.getElementById("cliente-disponible"),
      disponibleTitulo: document.getElementById("cliente-disponible-titulo"),
      vencida: document.getElementById("cliente-vencida"),
      aviso: document.getElementById("cliente-aviso"),
    };
    function elegirCliente(c) {
      cliente = c;
      mostrarErrores([]);
      dibujar();
      persistir();
      confirmar.focus();
    }

    function dibujar() {
      const visible = activo();
      bloque.classList.toggle("hidden", !visible);
      elegir.classList.toggle("hidden", Boolean(cliente));
      elegido.classList.toggle("hidden", !cliente);
      if (!visible || !cliente) return;
      const resumen = resumenDeCliente(cliente, totalActual);
      campos.nombre.textContent = cliente.nombre;
      campos.saldo.textContent = resumen.saldo;
      campos.limite.textContent = resumen.limite;
      campos.disponible.textContent = resumen.disponible || "";
      campos.disponible.classList.toggle("hidden", !resumen.disponible);
      campos.disponibleTitulo.classList.toggle("hidden", !resumen.disponible);
      campos.vencida.textContent = resumen.vencida || "";
      campos.vencida.classList.toggle("hidden", !resumen.vencida);
      campos.aviso.textContent = resumen.aviso || "";
      campos.aviso.classList.toggle("hidden", !resumen.aviso);
    }

    function activo() {
      return medio.value !== "" && medio.value === raiz.dataset.cuentaCorriente;
    }

    // Una venta guardada en la pestaña trae el cliente con datos de antes: se vuelven a pedir.
    async function refrescar() {
      if (!cliente) return;
      const anterior = cliente;
      const datos = await consultarClientes(raiz.dataset.clientes, anterior.nombre);
      const actual = datos.resultados.find((c) => c.id === anterior.id) || null;
      if (cliente === anterior) {
        cliente = actual;
        dibujar();
        persistir();
      }
    }

    // SC-01 con la navegación del buscador de productos (DEC-97).
    crearElegirCliente({
      entrada: buscarCliente,
      lista,
      url: raiz.dataset.clientes,
      alElegir: elegirCliente,
    });
    document.getElementById("cambiar-cliente").addEventListener("click", () => {
      cliente = null;
      dibujar();
      persistir();
      buscarCliente.focus();
    });

    return {
      dibujar,
      mostrar() {
        dibujar();
        if (activo() && !cliente) buscarCliente.focus();
      },
      refrescar,
      activo,
    };
  })();

  medio.addEventListener("change", () => {
    cuentaCorriente.mostrar();
    persistir();
  });

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
    cliente = null;
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
      // Solo con cuenta corriente; con otro medio el servidor no lo usa (SC-03).
      cliente: cuentaCorriente.activo() && cliente ? String(cliente.id) : "",
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

  // L11 (DEC-176): al retomar, el aviso usa el stock actual del servidor. Mientras llega, o si
  // no llega, las líneas no avisan.
  async function refrescarStock() {
    if (lineas.size === 0) return;
    try {
      const ids = [...lineas.keys()].join(",");
      const respuesta = await fetch(`${raiz.dataset.stock}?ids=${ids}`, {
        headers: { Accept: "application/json" },
      });
      if (!respuesta.ok) return;
      const datos = await respuesta.json();
      for (const linea of conStockActual([...lineas.values()], datos.stock || {})) {
        const actual = lineas.get(linea.producto.id);
        // Solo el stock: la cantidad puede haber cambiado mientras llegaba la respuesta.
        if (actual) actual.producto = { ...actual.producto, stock: linea.producto.stock };
      }
      dibujarTotales();
    } catch {
      // Sin respuesta: la venta sigue sin aviso de stock.
    }
  }

  const previa = guardada.leer();
  if (previa) {
    for (const linea of conStockActual(previa.lineas, {})) lineas.set(linea.producto.id, linea);
    if ([...medio.options].some((opcion) => opcion.value === previa.medio)) medio.value = previa.medio;
    cliente = previa.cliente;
  }
  dibujar();
  cuentaCorriente.refrescar();
  if (previa) refrescarStock();
})();
