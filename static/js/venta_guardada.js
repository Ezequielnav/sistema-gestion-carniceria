// Venta en curso guardada en sessionStorage (DEC-47): sobrevive a salir de la pantalla y
// volver en la misma pestaña. Se borra al confirmar o vaciar la venta. Lógica pura, probada
// con `node --test`; si el navegador no deja guardar, la venta sigue funcionando sin guardarse.
(function (raiz) {
  "use strict";

  function crearVentaGuardada(almacen, clave) {
    return {
      // lineas: [{ producto, cantidad }]; medio: id del medio de pago elegido o "";
      // cliente: el de la cuenta corriente (SC-03, DEC-123) o null.
      guardar(lineas, medio, cliente = null) {
        try {
          if (lineas.length === 0) almacen.removeItem(clave);
          else almacen.setItem(clave, JSON.stringify({ lineas, medio, cliente }));
        } catch {
          // Sin almacenamiento disponible: no se guarda.
        }
      },
      leer() {
        try {
          const datos = JSON.parse(almacen.getItem(clave));
          if (!datos || !Array.isArray(datos.lineas)) return null;
          const lineas = datos.lineas.filter(
            (l) => l && l.producto && Number.isInteger(l.producto.id) && typeof l.cantidad === "string",
          );
          if (!lineas.length) return null;
          const cliente = datos.cliente && Number.isInteger(datos.cliente.id) ? datos.cliente : null;
          return { lineas, medio: typeof datos.medio === "string" ? datos.medio : "", cliente };
        } catch {
          return null;
        }
      },
      borrar() {
        try {
          almacen.removeItem(clave);
        } catch {
          // Nada que borrar.
        }
      },
    };
  }

  // L11 (DEC-165, DEC-176): al retomar, el stock guardado puede ser viejo. Devuelve las líneas
  // con el stock del servidor (`stockPorId`: id -> texto, o null sin control de stock); un
  // producto que no vino queda sin stock y sin aviso. Con `{}`, ninguna línea avisa.
  function conStockActual(lineas, stockPorId) {
    return lineas.map((linea) => {
      const valor = stockPorId[String(linea.producto.id)];
      return { ...linea, producto: { ...linea.producto, stock: valor === undefined ? null : valor } };
    });
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { crearVentaGuardada, conStockActual };
  else {
    raiz.crearVentaGuardada = crearVentaGuardada;
    raiz.conStockActual = conStockActual;
  }
})(typeof window !== "undefined" ? window : globalThis);
