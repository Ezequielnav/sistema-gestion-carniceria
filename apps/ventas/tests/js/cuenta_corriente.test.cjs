// SC-03 en la venta (DEC-108, DEC-109, DEC-115, DEC-123): resumen del cliente elegido.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { resumenDeCliente } = require(path.join(__dirname, "../../../../static/js/cuenta_corriente.js"));

// Intl.NumberFormat separa con espacio duro: se compara sin depender de eso.
const limpiar = (texto) => texto && texto.replace(/\s/g, " ");

const juan = {
  id: 1,
  nombre: "Juan Pérez",
  saldo: "800.00",
  limite: "$ 1.000,00",
  disponible: "200.00",
  deuda_vencida: "0.00",
};

test("muestra saldo, límite y disponible, sin aviso si la venta entra", () => {
  const resumen = resumenDeCliente(juan, 200);

  assert.equal(limpiar(resumen.saldo), "$ 800,00");
  assert.equal(resumen.limite, "$ 1.000,00");
  assert.equal(limpiar(resumen.disponible), "$ 200,00");
  assert.equal(resumen.vencida, null);
  assert.equal(resumen.aviso, null);
});

test("avisa si la venta supera el disponible", () => {
  assert.equal(limpiar(resumenDeCliente(juan, 200.01).aviso), "La venta supera el disponible de $ 200,00.");
});

test("sin límite no hay disponible ni aviso", () => {
  const resumen = resumenDeCliente({ ...juan, limite: "Sin límite", disponible: null }, 999999);

  assert.equal(resumen.disponible, null);
  assert.equal(resumen.aviso, null);
});

test("con límite 0 avisa que no tiene crédito habilitado", () => {
  const resumen = resumenDeCliente({ ...juan, saldo: "0.00", limite: "Sin crédito habilitado", disponible: "0.00" }, 0);

  assert.equal(resumen.aviso, "Este cliente no tiene crédito habilitado.");
});

test("un saldo por encima del límite muestra disponible 0", () => {
  const resumen = resumenDeCliente({ ...juan, saldo: "1500.00", disponible: "-500.00" }, 10);

  assert.equal(limpiar(resumen.disponible), "$ 0,00");
  assert.equal(limpiar(resumen.aviso), "La venta supera el disponible de $ 0,00.");
});

test("la deuda vencida es una alerta aparte", () => {
  const resumen = resumenDeCliente({ ...juan, deuda_vencida: "400.00" }, 100);

  assert.equal(limpiar(resumen.vencida), "Tiene deuda vencida: $ 400,00.");
  assert.equal(resumen.aviso, null);
});
