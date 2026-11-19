// DEC-202: cada campo de contraseña lleva un botón con un ojo para ver lo que se escribió.
// Arranca oculta; el botón dice qué va a hacer ("Mostrar contraseña" u "Ocultar contraseña")
// y marca con aria-pressed si está a la vista. Íconos de Lucide (licencia ISC).
(function (raiz) {
  "use strict";

  const OJO =
    '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>';
  const OJO_TACHADO =
    '<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/>';

  // Qué muestra el campo y qué dice el botón según la contraseña esté a la vista o no.
  function estadoOjo(visible) {
    return visible
      ? { tipo: "text", etiqueta: "Ocultar contraseña", icono: OJO_TACHADO }
      : { tipo: "password", etiqueta: "Mostrar contraseña", icono: OJO };
  }

  function agregarOjo(campo, documento) {
    const caja = documento.createElement("div");
    caja.className = "campo-con-ojo";
    campo.parentNode.insertBefore(caja, campo);
    caja.appendChild(campo);

    const boton = documento.createElement("button");
    boton.type = "button";
    boton.className = "boton-ojo";
    boton.dataset.ojo = "";
    boton.setAttribute("aria-controls", campo.id);
    caja.appendChild(boton);

    function dibujar(visible) {
      const estado = estadoOjo(visible);
      campo.type = estado.tipo;
      boton.setAttribute("aria-label", estado.etiqueta);
      boton.setAttribute("aria-pressed", String(visible));
      boton.title = estado.etiqueta;
      boton.innerHTML =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="size-5" aria-hidden="true">' +
        estado.icono +
        "</svg>";
    }

    boton.addEventListener("click", () => {
      dibujar(campo.type === "password");
      campo.focus();
    });
    // Al enviar el formulario la contraseña vuelve a ocultarse: no queda a la vista si la
    // página tarda o se vuelve atrás.
    if (campo.form) campo.form.addEventListener("submit", () => dibujar(false));
    dibujar(false);
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { estadoOjo };
    return;
  }
  raiz.document.addEventListener("DOMContentLoaded", () => {
    for (const campo of raiz.document.querySelectorAll('input[type="password"]')) {
      agregarOjo(campo, raiz.document);
    }
  });
})(typeof window !== "undefined" ? window : globalThis);
