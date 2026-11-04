// DEC-47: la venta en curso se guarda en sessionStorage y se borra al confirmar o vaciar.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { crearVentaGuardada } = require(path.join(__dirname, "../../../../static/js/venta_guardada.js"));

function almacenDePrueba() {
  const datos = new Map();
  return {
    getItem: (clave) => (datos.has(clave) ? datos.get(clave) : null),
    setItem: (clave, valor) => datos.set(clave, String(valor)),
    removeItem: (clave) => datos.delete(clave),
    datos,
  };
}

const pan = { id: 7, nombre: "Pan", plus: "", precio: "100.00", unidad: "UNIDAD" };
const queso = { id: 9, nombre: "Queso", plus: "205", precio: "8000.00", unidad: "KG" };

test("guarda las líneas y el medio, y los devuelve al volver a la pantalla", () => {
  const almacen = almacenDePrueba();
  crearVentaGuardada(almacen, "venta-en-curso-3").guardar(
    [{ producto: pan, cantidad: "2" }, { producto: queso, cantidad: "0.750" }],
    "1",
  );

  assert.deepEqual(crearVentaGuardada(almacen, "venta-en-curso-3").leer(), {
    lineas: [{ producto: pan, cantidad: "2" }, { producto: queso, cantidad: "0.750" }],
    medio: "1",
    cliente: null,
  });
});

test("con cuenta corriente guarda también el cliente elegido (DEC-123)", () => {
  const almacen = almacenDePrueba();
  const juan = { id: 4, nombre: "Juan Pérez", saldo: "800.00" };
  crearVentaGuardada(almacen, "venta-en-curso-3").guardar([{ producto: pan, cantidad: "1" }], "5", juan);

  assert.deepEqual(crearVentaGuardada(almacen, "venta-en-curso-3").leer().cliente, juan);
});

test("un cliente guardado sin id válido se descarta", () => {
  const almacen = almacenDePrueba();
  almacen.setItem(
    "venta-en-curso-3",
    JSON.stringify({ lineas: [{ producto: pan, cantidad: "1" }], medio: "5", cliente: { id: "4" } }),
  );

  assert.equal(crearVentaGuardada(almacen, "venta-en-curso-3").leer().cliente, null);
});

test("una venta vacía no deja nada guardado", () => {
  const almacen = almacenDePrueba();
  const guardada = crearVentaGuardada(almacen, "venta-en-curso-3");
  guardada.guardar([{ producto: pan, cantidad: "1" }], "");
  guardada.guardar([], "");

  assert.equal(guardada.leer(), null);
  assert.equal(almacen.datos.size, 0);
});

test("borrar (al confirmar o vaciar) elimina la venta guardada", () => {
  const almacen = almacenDePrueba();
  const guardada = crearVentaGuardada(almacen, "venta-en-curso-3");
  guardada.guardar([{ producto: pan, cantidad: "1" }], "2");
  guardada.borrar();

  assert.equal(guardada.leer(), null);
});

test("cada usuario tiene su propia venta guardada", () => {
  const almacen = almacenDePrueba();
  crearVentaGuardada(almacen, "venta-en-curso-3").guardar([{ producto: pan, cantidad: "1" }], "");

  assert.equal(crearVentaGuardada(almacen, "venta-en-curso-4").leer(), null);
});

test("datos dañados o líneas inválidas se ignoran", () => {
  const almacen = almacenDePrueba();
  almacen.setItem("roto", "{no es json");
  almacen.setItem("raro", JSON.stringify({ lineas: [{ producto: { id: "x" }, cantidad: 1 }] }));

  assert.equal(crearVentaGuardada(almacen, "roto").leer(), null);
  assert.equal(crearVentaGuardada(almacen, "raro").leer(), null);
});

test("si el navegador no deja guardar, no falla", () => {
  const fallido = {
    getItem() { throw new Error("bloqueado"); },
    setItem() { throw new Error("bloqueado"); },
    removeItem() { throw new Error("bloqueado"); },
  };
  const guardada = crearVentaGuardada(fallido, "venta-en-curso-3");

  assert.doesNotThrow(() => guardada.guardar([{ producto: pan, cantidad: "1" }], ""));
  assert.doesNotThrow(() => guardada.borrar());
  assert.equal(guardada.leer(), null);
});
