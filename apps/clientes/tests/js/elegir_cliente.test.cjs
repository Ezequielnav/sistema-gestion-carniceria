// DEC-206: qué dice la lista de SC-01 cuando no trae clientes.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { sinClientes } = require(path.join(__dirname, "../../../../static/js/elegir_cliente.js"));

test("con texto, avisa que no hay coincidencias", () => {
  assert.equal(sinClientes("juan", "cobro"), "No hay clientes que coincidan.");
  assert.equal(sinClientes("juan", ""), "No hay clientes que coincidan.");
});

test("sin texto, en el cobro avisa que nadie debe y en la venta que no hay activos", () => {
  assert.equal(sinClientes("", "cobro"), "No hay clientes con saldo para cobrar.");
  assert.equal(sinClientes("", ""), "No hay clientes activos.");
});
