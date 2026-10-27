// Venta en curso guardada en sessionStorage (DEC-47): sobrevive a salir de la pantalla y
// volver en la misma pestaña. Se borra al confirmar o vaciar la venta. Lógica pura, probada
// con `node --test`; si el navegador no deja guardar, la venta sigue funcionando sin guardarse.
(function (raiz) {
  "use strict";

  function crearVentaGuardada(almacen, clave) {
    return {
      // lineas: [{ producto, cantidad }]; medio: id del medio de pago elegido o "".
      guardar(lineas, medio) {
        try {
          if (lineas.length === 0) almacen.removeItem(clave);
          else almacen.setItem(clave, JSON.stringify({ lineas, medio }));
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
          return lineas.length ? { lineas, medio: typeof datos.medio === "string" ? datos.medio : "" } : null;
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
