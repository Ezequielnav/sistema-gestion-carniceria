// CP-110 (DEC-102, DEC-103): avisa con la cantidad disponible y sin bloquear.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { avisoDeStock } = require(path.join(__dirname, "../../../../static/js/aviso_stock.js"));

const aceite = { unidad: "UNIDAD", stock: "3.000" };
const bondiola = { unidad: "KG", stock: "1.250" };

test("con stock suficiente no avisa, tampoco con la cantidad justa", () => {
  assert.equal(avisoDeStock(aceite, "1"), null);
  assert.equal(avisoDeStock(aceite, "3"), null);
  assert.equal(avisoDeStock(bondiola, ""), null); // peso todavía sin cargar
  assert.equal(avisoDeStock(bondiola, "1,25"), null);
});

test("si la cantidad supera el stock, muestra lo disponible según la unidad", () => {
  assert.match(avisoDeStock(aceite, "4"), /disponible 3\./);
  assert.match(avisoDeStock(bondiola, "1.5"), /disponible 1,250 kg\./);
  assert.match(avisoDeStock(aceite, "4"), /Se puede vender igual/);
});

test("sin stock avisa al agregar, aunque el peso esté vacío", () => {
  assert.match(avisoDeStock({ unidad: "KG", stock: "0.000" }, ""), /Sin stock/);
  assert.match(avisoDeStock({ unidad: "UNIDAD", stock: "-2.000" }, "1"), /Sin stock/);
});

test("sin control de stock o con una venta guardada sin el dato, no avisa", () => {
  assert.equal(avisoDeStock({ unidad: "KG", stock: null }, "50"), null);
  assert.equal(avisoDeStock({ unidad: "KG" }, "50"), null);
});
