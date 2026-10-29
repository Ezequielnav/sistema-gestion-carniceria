// Lista de productos del buscador de la venta (DEC-97). Filtra mientras se escribe, pero
// espera a que se deje de escribir: el lector (DEC-37) escribe el código muy rápido y
// termina con Enter, que descarta el filtro pendiente y busca el plus exacto (DEC-52).
// Lógica pura, probada con `node --test`.
(function (raiz) {
  "use strict";

  const ESPERA_MS = 250; // sin teclas durante este tiempo, se filtra

  function crearBuscadorDiferido({
    espera = ESPERA_MS,
    programar = (funcion, ms) => setTimeout(funcion, ms),
    cancelarProgramado = (id) => clearTimeout(id),
  } = {}) {
    let pendiente = null;
    let turno = 0;

    function descartar() {
      if (pendiente !== null) cancelarProgramado(pendiente);
      pendiente = null;
      turno += 1;
    }

    return {
      // Cada tecla reprograma el filtro; `consultar(texto, turno)` corre al dejar de escribir.
      diferir(texto, consultar) {
        descartar();
        const mio = turno;
        pendiente = programar(() => {
          pendiente = null;
          consultar(texto, mio);
        }, espera);
      },
      // Enter, abrir la lista o agregar: descarta lo pendiente y las respuestas en camino.
      inmediato() {
        descartar();
        return turno;
      },
      descartar,
      // Una respuesta se muestra solo si nada la reemplazó mientras llegaba.
      vigente(suTurno) {
        return suTurno === turno;
      },
    };
  }

  // Flechas, Inicio y Fin sobre la lista; -1 es "ninguno marcado".
  function moverSeleccion(actual, cantidad, tecla) {
    if (cantidad === 0) return -1;
    if (tecla === "ArrowDown") return Math.min(actual + 1, cantidad - 1);
    if (tecla === "ArrowUp") return Math.max(actual - 1, 0);
    if (tecla === "Home") return 0;
    if (tecla === "End") return cantidad - 1;
    return actual;
  }

  const exportado = { crearBuscadorDiferido, moverSeleccion };
  if (typeof module !== "undefined" && module.exports) module.exports = exportado;
  else Object.assign(raiz, exportado);
})(typeof window !== "undefined" ? window : globalThis);
