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

  if (typeof module !== "undefined" && module.exports) module.exports = { crearVentaGuardada };
  else raiz.crearVentaGuardada = crearVentaGuardada;
})(typeof window !== "undefined" ? window : globalThis);
