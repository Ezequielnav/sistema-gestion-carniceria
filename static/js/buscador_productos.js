// Buscador de productos común a la venta (CU-01) y al ingreso de mercadería (CU-05) (L13,
// DEC-181). Es el combo del buscador con su lista: filtra al dejar de escribir y se recorre con
// flechas, Inicio, Fin, Enter y Escape (DEC-97), con la lógica de buscador.js
// (`crearBuscadorDiferido`, `moverSeleccion`, `textoAlAbrir`), que hay que cargar antes. Cada
// pantalla pasa lo que cambia entre las dos: cómo consulta, qué muestra en cada opción, qué hace
// al elegir y las opciones de abajo.
(function (raiz) {
  "use strict";

  // consultar(texto) -> Promise<{ exacto?, resultados, hay_mas }>
  // detalle(producto) -> texto de la derecha de cada opción (precio de venta o de compra)
  // sinResultados(texto) -> el <li> que se muestra si la búsqueda no trae nada
  // alElegir(producto) -> agrega a la pantalla
  // Opciones de la venta (en el ingreso quedan apagadas):
  //   exactoConEnter: Enter con un código exacto lo agrega (lector, DEC-37 y DEC-52)
  //   abrirSinTexto: el clic en el buscador vacío, la flecha abajo y `boton` abren la lista
  //   marcarConMouse: pasar el mouse por una opción la marca
  function crearBuscadorProductos({
    entrada,
    lista,
    boton = null,
    consultar,
    detalle,
    sinResultados,
    alElegir,
    exactoConEnter = false,
    abrirSinTexto = false,
    marcarConMouse = false,
  }) {
    const buscador = raiz.crearBuscadorDiferido();
    let visibles = [];
    let marcado = -1;

    function marcar(indice) {
      const opciones = lista.querySelectorAll("[role=option]");
      marcado = indice;
      opciones.forEach((opcion, i) => {
        opcion.setAttribute("aria-selected", String(i === marcado));
        opcion.classList.toggle("opcion-marcada", i === marcado);
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
      li.className = "opcion-vacia";
      li.textContent = texto;
      return li;
    }

    function mostrar(productos, texto, hayMas) {
      lista.replaceChildren();
      visibles = productos;
      if (productos.length === 0) lista.append(sinResultados(texto));
      productos.forEach((producto, i) => {
        const opcion = document.createElement("li");
        opcion.id = `producto-${producto.id}`;
        opcion.setAttribute("role", "option");
        opcion.className = "opcion";
        const nombre = document.createElement("span");
        nombre.textContent = producto.plus ? `${producto.nombre} (${producto.plus})` : producto.nombre;
        const derecha = document.createElement("span");
        derecha.className = "monto whitespace-nowrap font-normal text-tinta-suave";
        derecha.textContent = detalle(producto);
        opcion.append(nombre, derecha);
        // mousedown evita que el clic saque el foco del buscador antes de elegir.
        opcion.addEventListener("mousedown", (evento) => evento.preventDefault());
        opcion.addEventListener("click", () => alElegir(producto));
        if (marcarConMouse) opcion.addEventListener("mousemove", () => marcado !== i && marcar(i));
        lista.append(opcion);
      });
      if (hayMas) lista.append(aviso("Seguí escribiendo para ver más."));
      lista.classList.remove("hidden");
      entrada.setAttribute("aria-expanded", "true");
      marcar(-1);
    }

    async function filtrar(texto, turno) {
      const datos = await consultar(texto);
      if (buscador.vigente(turno)) mostrar(datos.resultados, texto, datos.hay_mas);
    }

    // Enter con texto. En la venta, el código exacto se agrega (DEC-52); si no, se muestra la lista.
    async function buscarTexto(texto) {
      const turno = buscador.inmediato();
      const datos = await consultar(texto);
      if (!buscador.vigente(turno)) return;
      if (exactoConEnter && datos.exacto) {
        alElegir(datos.exacto);
        return;
      }
      entrada.value = texto;
      mostrar(datos.resultados, texto, datos.hay_mas);
      entrada.focus();
    }

    function abrir(desde) {
      const texto = raiz.textoAlAbrir(desde, entrada.value);
      if (!texto) entrada.value = "";
      filtrar(texto, buscador.inmediato());
    }

    if (abrirSinTexto) {
      // DEC-97: la lista se abre a pedido, nunca sola al volver el foco después de agregar.
      entrada.addEventListener("click", () => {
        if (!entrada.value.trim()) abrir();
      });
      if (boton) {
        boton.addEventListener("click", () => {
          abrir("boton");
          entrada.focus();
        });
      }
    }

    entrada.addEventListener("input", () => {
      marcar(-1);
      const texto = entrada.value.trim();
      // En la venta, sin texto se filtra igual y muestra todos; en el ingreso, se cierra.
      if (texto || abrirSinTexto) buscador.diferir(texto, filtrar);
      else cerrar();
    });

    entrada.addEventListener("keydown", (evento) => {
      const abierta = !lista.classList.contains("hidden");
      const flecha = ["ArrowDown", "ArrowUp", "Home", "End"].includes(evento.key);
      if (flecha && (abierta || (abrirSinTexto && evento.key === "ArrowDown"))) {
        evento.preventDefault();
        if (abierta) marcar(raiz.moverSeleccion(marcado, visibles.length, evento.key));
        else abrir();
        return;
      }
      if (evento.key === "Escape" && abierta) {
        evento.preventDefault();
        cerrar();
        return;
      }
      if (evento.key !== "Enter") return;
      evento.preventDefault();
      // Un producto marcado con las flechas; si no, la búsqueda del texto.
      if (abierta && marcado >= 0) {
        alElegir(visibles[marcado]);
        return;
      }
      const texto = entrada.value.trim();
      if (texto) buscarTexto(texto);
    });

    document.addEventListener("click", (evento) => {
      const partes = [entrada, lista, boton].filter(Boolean);
      if (!partes.some((parte) => parte.contains(evento.target))) cerrar();
    });

    return { buscarTexto, cerrar };
  }

  raiz.crearBuscadorProductos = crearBuscadorProductos;
})(window);
