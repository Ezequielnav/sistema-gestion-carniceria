// DEC-202: el ojo de los campos de contraseña.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { estadoOjo } = require(path.join(__dirname, "../../../../static/js/contrasena.js"));

test("oculta, el campo es de contraseña y el botón ofrece mostrarla", () => {
  const estado = estadoOjo(false);
  assert.equal(estado.tipo, "password");
  assert.equal(estado.etiqueta, "Mostrar contraseña");
});

test("a la vista, el campo es de texto y el botón ofrece ocultarla con el ojo tachado", () => {
  const estado = estadoOjo(true);
  assert.equal(estado.tipo, "text");
  assert.equal(estado.etiqueta, "Ocultar contraseña");
  assert.match(estado.icono, /m2 2 20 20/);
});
