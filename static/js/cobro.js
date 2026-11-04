// CU-04: elegir el cliente con SC-01 (incluidos los dados de baja que deben, DEC-116) y
// mostrar su saldo como máximo a cobrar (DEC-111). El servidor vuelve a validar todo.
(function () {
  "use strict";

  const formulario = document.getElementById("cobro");
  if (!formulario) return;

  const campoCliente = document.getElementById("id_cliente");
  const monto = document.getElementById("id_monto");
  const elegir = document.getElementById("elegir-cliente");
  const buscar = document.getElementById("buscar-cliente");
  const elegido = document.getElementById("cliente-elegido");
  const pesos = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function mostrar(cliente) {
    campoCliente.value = cliente ? String(cliente.id) : "";
    elegir.classList.toggle("hidden", Boolean(cliente));
    elegido.classList.toggle("hidden", !cliente);
    if (!cliente) {
      monto.removeAttribute("max");
      return;
    }
    document.getElementById("cliente-nombre").textContent = cliente.nombre;
    document.getElementById("cliente-baja").classList.toggle("hidden", cliente.activo);
    document.getElementById("cliente-saldo").textContent = `$ ${pesos.format(Number(cliente.saldo))}`;
    const vencida = Number(cliente.deuda_vencida);
    const alerta = document.getElementById("cliente-vencida");
    alerta.textContent = vencida > 0 ? `Tiene deuda vencida: $ ${pesos.format(vencida)}.` : "";
    alerta.classList.toggle("hidden", !(vencida > 0));
    monto.max = cliente.saldo;
  }

  crearElegirCliente({
    entrada: buscar,
    lista: document.getElementById("clientes"),
    url: formulario.dataset.clientes,
    para: "cobro",
    alElegir(cliente) {
      mostrar(cliente);
      monto.focus();
    },
  });

  document.getElementById("cambiar-cliente").addEventListener("click", () => {
    mostrar(null);
    buscar.focus();
  });

  mostrar(JSON.parse(document.getElementById("cliente-inicial").textContent));
  if (!campoCliente.value) buscar.focus();
})();
