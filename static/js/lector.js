// Detección del lector de códigos en un campo de cantidad (DF-01, DEC-75).
// El lector funciona como teclado (DEC-37): escribe el código muy rápido y termina con Enter.
// Una persona tecleando deja más tiempo entre teclas. Lógica pura, probada con `node --test`.
(function (raiz) {
  "use strict";

  const INTERVALO_MAXIMO_MS = 50; // entre teclas de una misma lectura
  const LARGO_MINIMO = 3; // lecturas más cortas se toman como tecleo (supuesto de DEC-75)

  function crearDetectorLector({ intervaloMaximo = INTERVALO_MAXIMO_MS, largoMinimo = LARGO_MINIMO } = {}) {
    let rafaga = null;

    return {
      // Una tecla imprimible: `valorAntes` es lo que tenía el campo antes de esa tecla.
      tecla(caracter, instante, valorAntes) {
        if (rafaga && instante - rafaga.ultimo <= intervaloMaximo) {
          rafaga.texto += caracter;
        } else {
          rafaga = { texto: caracter, valorPrevio: valorAntes };
        }
        rafaga.ultimo = instante;
      },
      // Enter: devuelve la lectura del lector ({ texto, valorPrevio }) o null si tecleó una persona.
      enter(instante) {
        const lectura = rafaga;
        rafaga = null;
        if (!lectura || instante - lectura.ultimo > intervaloMaximo) return null;
        if (lectura.texto.length < largoMinimo) return null;
        return { texto: lectura.texto, valorPrevio: lectura.valorPrevio };
      },
      olvidar() {
        rafaga = null;
      },
    };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { crearDetectorLector };
  else raiz.crearDetectorLector = crearDetectorLector;
})(typeof window !== "undefined" ? window : globalThis);
