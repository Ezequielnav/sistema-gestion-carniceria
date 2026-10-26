// DF-01 y DEC-75: una lectura del lector en el campo de peso se separa de la cantidad.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { crearDetectorLector } = require(path.join(__dirname, "../../../../static/js/lector.js"));

function teclear(detector, texto, desde, intervalo, valorInicial) {
  let valor = valorInicial;
  let instante = desde;
  for (const caracter of texto) {
    detector.tecla(caracter, instante, valor);
    valor += caracter;
    instante += intervalo;
  }
  return { valor, instante: instante - intervalo };
}

test("la cajera tecleando un peso no es una lectura: Enter vuelve al buscador", () => {
  const detector = crearDetectorLector();
  const { instante } = teclear(detector, "0.750", 1000, 180, "");
  assert.equal(detector.enter(instante + 300), null);
});

test("una lectura rápida después del peso se separa y la cantidad vuelve al valor previo", () => {
  const detector = crearDetectorLector();
  const peso = teclear(detector, "0.750", 1000, 180, "");
  const lectura = teclear(detector, "601", peso.instante + 900, 5, peso.valor);
  assert.deepEqual(detector.enter(lectura.instante + 5), { texto: "601", valorPrevio: "0.750" });
});

test("un peso entero seguido de un código no queda como 1601 kg", () => {
  const detector = crearDetectorLector();
  const peso = teclear(detector, "1", 1000, 0, "");
  const lectura = teclear(detector, "601", peso.instante + 700, 4, peso.valor);
  assert.deepEqual(detector.enter(lectura.instante + 4), { texto: "601", valorPrevio: "1" });
});

test("lecturas de menos de 3 caracteres se toman como tecleo", () => {
  const detector = crearDetectorLector();
  const { instante } = teclear(detector, "12", 1000, 5, "");
  assert.equal(detector.enter(instante + 5), null);
});

test("un Enter que llega tarde después de una ráfaga no es del lector", () => {
  const detector = crearDetectorLector();
  const { instante } = teclear(detector, "601", 1000, 5, "");
  assert.equal(detector.enter(instante + 400), null);
});

test("después de un Enter la ráfaga se olvida", () => {
  const detector = crearDetectorLector();
  const { instante } = teclear(detector, "601", 1000, 5, "");
  assert.notEqual(detector.enter(instante + 5), null);
  assert.equal(detector.enter(instante + 10), null);
});
