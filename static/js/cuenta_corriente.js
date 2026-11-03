// SC-03 en la venta (DEC-123): qué se muestra del cliente elegido (SC-01) y si la venta
// pasaría su límite. Es orientativo: el servidor vuelve a validar todo al confirmar (DEC-47).
// Lógica pura, probada con `node --test`.
(function (raiz) {
  "use strict";

  const pesos = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function plata(valor) {
    return `$ ${pesos.format(Number(valor))}`;
  }

  // `cliente` viene de /clientes/buscar/: montos como texto, `disponible` null sin límite y
  // `limite` ya escrito como lo muestra DEC-115. `total` es el total de la venta en pantalla.
  function resumenDeCliente(cliente, total) {
    const disponible = cliente.disponible === null ? null : Number(cliente.disponible);
    const vencida = Number(cliente.deuda_vencida);
    let aviso = null;
    if (cliente.limite === "Sin crédito habilitado") {
      aviso = "Este cliente no tiene crédito habilitado.";
    } else if (disponible !== null && total > disponible) {
      aviso = `La venta supera el disponible de ${plata(Math.max(disponible, 0))}.`;
    }
    return {
      saldo: plata(cliente.saldo),
      limite: cliente.limite,
      disponible: disponible === null ? null : plata(Math.max(disponible, 0)),
      // DEC-109: solo alerta, no frena la venta.
      vencida: vencida > 0 ? `Tiene deuda vencida: ${plata(vencida)}.` : null,
      aviso,
    };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { resumenDeCliente };
  else raiz.resumenDeCliente = resumenDeCliente;
})(typeof window !== "undefined" ? window : globalThis);
