// Aviso de stock insuficiente en la venta (CU-01 A3, DEC-46, DEC-102, DEC-103): muestra la
// cantidad disponible y no bloquea. Lógica pura, probada con `node --test`.
(function (raiz) {
  "use strict";

  function disponible(stock, unidad) {
    if (unidad === "KG") {
      const kg = stock.toLocaleString("es-AR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
      return `${kg} kg`;
    }
    return stock.toLocaleString("es-AR", { maximumFractionDigits: 0 });
  }

  // `producto.stock` es null sin control de stock (la carne). `cantidad` es lo escrito en la
  // línea; un peso todavía vacío cuenta como 0. Devuelve el texto o null si alcanza.
  function avisoDeStock(producto, cantidad) {
    if (producto.stock === null || producto.stock === undefined) return null;
    const stock = Number(producto.stock);
    const pedida = Number(String(cantidad).replace(",", ".")) || 0;
    if (stock > 0 && pedida <= stock) return null;
    if (stock <= 0) return "Sin stock. Se puede vender igual.";
    return `Stock insuficiente: disponible ${disponible(stock, producto.unidad)}. Se puede vender igual.`;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { avisoDeStock };
  else raiz.avisoDeStock = avisoDeStock;
})(typeof window !== "undefined" ? window : globalThis);
