// DEC-106: "Sale de la caja abierta" se muestra solo si el medio elegido es el efectivo.
(function () {
  "use strict";

  const bloque = document.querySelector("[data-sale-de-caja]");
  const medio = document.getElementById("id_medio_pago");
  if (!bloque || !medio) return;

  function mostrar() {
    bloque.classList.toggle("hidden", !medio.value || medio.value !== bloque.dataset.efectivo);
  }

  medio.addEventListener("change", mostrar);
  mostrar();
})();
