// Gráficos de la pestaña "Resumen" de Reportes (DEC-158), con Chart.js 4.4.9 como archivo propio.
// Los montos llegan como texto desde el servidor y se convierten a número solo para dibujar.
(function () {
  "use strict";

  const fuente = document.getElementById("datos-resumen");
  if (!fuente || !window.Chart) return;
  const datos = JSON.parse(fuente.textContent);

  // S-11 (DEC-197): los colores salen de las variables CSS del tema (static/src/estilos.css),
  // para que un cambio de paleta no toque este archivo.
  const tema = getComputedStyle(document.documentElement);
  const color = (nombre, respaldo) => tema.getPropertyValue(nombre).trim() || respaldo;
  const SERIE = color("--color-marino-700", "#1d3a7a");
  const GRILLA = color("--color-borde", "#e3dacb");
  const TEXTO = color("--color-tinta-suave", "#625a50");
  // Relleno de la línea: la serie al 8 %.
  const SERIE_SUAVE = conTransparencia(SERIE, 0.08);

  function conTransparencia(hex, alfa) {
    const valor = /^#([0-9a-f]{6})$/i.exec(hex);
    if (!valor) return hex;
    const n = parseInt(valor[1], 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
  }
  const pesosExactos = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" });
  // En los ejes, abreviado ("$ 2 M") para que entre también en el celular.
  const pesosAbreviados = new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    notation: "compact",
    maximumFractionDigits: 1,
  });
  const numeros = (valores) => valores.map(Number);

  Chart.defaults.font.family = '"Source Sans 3", ui-sans-serif, system-ui, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = TEXTO;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.plugins.tooltip.callbacks.label = (contexto) =>
    pesosExactos.format(contexto.parsed[contexto.chart.options.indexAxis === "y" ? "x" : "y"]);
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    Chart.defaults.animation = false;
  }

  const ejeEnPesos = {
    beginAtZero: true,
    grid: { color: GRILLA },
    ticks: { maxTicksLimit: 5, maxRotation: 0, callback: (v) => pesosAbreviados.format(v) },
  };
  const ejeSinGrilla = { grid: { display: false } };
  const angosto = window.matchMedia("(max-width: 639px)").matches;

  function dibujar(id, configuracion) {
    const lienzo = document.getElementById(id);
    if (lienzo) new Chart(lienzo, configuracion);
  }

  dibujar("grafico-ventas", {
    type: "line",
    data: {
      labels: datos.serie.etiquetas,
      datasets: [
        {
          data: numeros(datos.serie.valores),
          borderColor: SERIE,
          backgroundColor: SERIE_SUAVE,
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: SERIE,
        },
      ],
    },
    options: {
      layout: { padding: { right: 12 } },
      interaction: { mode: "index", intersect: false },
      scales: { x: { ...ejeSinGrilla, ticks: { maxTicksLimit: angosto ? 5 : 8, maxRotation: 0 } }, y: ejeEnPesos },
    },
  });

  dibujar("grafico-medios", {
    type: "bar",
    data: {
      labels: datos.medios.etiquetas,
      datasets: [{ data: numeros(datos.medios.valores), backgroundColor: SERIE, borderRadius: 4, maxBarThickness: 28 }],
    },
    options: { indexAxis: "y", scales: { x: ejeEnPesos, y: ejeSinGrilla } },
  });

  dibujar("grafico-top", {
    type: "bar",
    data: {
      labels: datos.top.etiquetas,
      datasets: [{ data: numeros(datos.top.valores), backgroundColor: SERIE, borderRadius: 4, maxBarThickness: 28 }],
    },
    options: { indexAxis: "y", scales: { x: ejeEnPesos, y: ejeSinGrilla } },
  });
})();
