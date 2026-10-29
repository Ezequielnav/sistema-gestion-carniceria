// CP-106 y DEC-97: la lista filtra al dejar de escribir y no se mezcla con el lector.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { crearBuscadorDiferido, moverSeleccion, textoAlAbrir } = require(
  path.join(__dirname, "../../../../static/js/buscador.js"),
);

// Reloj falso: las tareas programadas corren solo al avanzar el tiempo.
function reloj() {
  let ahora = 0;
  let siguiente = 1;
  const tareas = new Map();
  return {
    programar(funcion, ms) {
      tareas.set(siguiente, { funcion, cuando: ahora + ms });
      return siguiente++;
    },
    cancelarProgramado(id) {
      tareas.delete(id);
    },
    avanzar(ms) {
      ahora += ms;
      for (const [id, tarea] of [...tareas]) {
        if (tarea.cuando <= ahora) {
          tareas.delete(id);
          tarea.funcion();
        }
      }
    },
  };
}

function escribir(buscador, r, texto, intervalo, consultar) {
  let valor = "";
  for (const caracter of texto) {
    valor += caracter;
    buscador.diferir(valor, consultar);
    r.avanzar(intervalo);
  }
}

test("tecleando, filtra una sola vez con el texto final al dejar de escribir", () => {
  const r = reloj();
  const buscador = crearBuscadorDiferido({ espera: 250, ...r });
  const consultas = [];
  escribir(buscador, r, "asa", 150, (texto) => consultas.push(texto));
  assert.deepEqual(consultas, []);
  r.avanzar(250);
  assert.deepEqual(consultas, ["asa"]);
});

test("el lector escribe rápido y termina con Enter: no se filtra nada", () => {
  const r = reloj();
  const buscador = crearBuscadorDiferido({ espera: 250, ...r });
  const consultas = [];
  escribir(buscador, r, "7791234567890", 5, (texto) => consultas.push(texto));
  buscador.inmediato(); // Enter: busca el plus exacto (DEC-52)
  r.avanzar(1000);
  assert.deepEqual(consultas, []);
});

test("una respuesta que llega después de agregar un producto no reabre la lista", () => {
  const r = reloj();
  const buscador = crearBuscadorDiferido({ espera: 250, ...r });
  let turnoDelFiltro;
  buscador.diferir("asa", (_, turno) => {
    turnoDelFiltro = turno;
  });
  r.avanzar(250);
  assert.ok(buscador.vigente(turnoDelFiltro));
  buscador.descartar(); // agregar o cerrar la lista
  assert.ok(!buscador.vigente(turnoDelFiltro));
});

test("abrir la lista invalida el filtro anterior y su respuesta es la vigente", () => {
  const r = reloj();
  const buscador = crearBuscadorDiferido({ espera: 250, ...r });
  const consultas = [];
  buscador.diferir("a", (texto) => consultas.push(texto));
  const turno = buscador.inmediato();
  r.avanzar(500);
  assert.deepEqual(consultas, []);
  assert.ok(buscador.vigente(turno));
});

test("las flechas recorren la lista sin salirse de sus bordes", () => {
  assert.equal(moverSeleccion(-1, 3, "ArrowDown"), 0);
  assert.equal(moverSeleccion(0, 3, "ArrowDown"), 1);
  assert.equal(moverSeleccion(2, 3, "ArrowDown"), 2);
  assert.equal(moverSeleccion(1, 3, "ArrowUp"), 0);
  assert.equal(moverSeleccion(0, 3, "ArrowUp"), 0);
  assert.equal(moverSeleccion(1, 3, "Home"), 0);
  assert.equal(moverSeleccion(0, 3, "End"), 2);
  assert.equal(moverSeleccion(-1, 0, "ArrowDown"), -1);
});

test("Ver productos muestra todos aunque el buscador tenga texto; clic y flecha usan lo escrito", () => {
  assert.equal(textoAlAbrir("boton", "zzz"), "");
  assert.equal(textoAlAbrir("boton", ""), "");
  assert.equal(textoAlAbrir("flecha", "  asa "), "asa");
  assert.equal(textoAlAbrir("clic", ""), "");
});
