// Gráficos de la pestaña "Resumen" de Reportes (DEC-158), con Chart.js 4.4.9 como archivo propio.
// Los montos llegan como texto desde el servidor y se convierten a número solo para dibujar.
(function () {
  "use strict";

  const fuente = document.getElementById("datos-resumen");
  if (!fuente || !window.Chart) return;
  const datos = JSON.parse(fuente.textContent);

  const ROJO = "#dc2626";
  const ROJO_SUAVE = "rgba(220, 38, 38, 0.08)";
  const GRILLA = "#f3f4f6";
  const pesosExactos = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" });
  // En los ejes, abreviado ("$ 2 M") para que entre también en el celular.
  const pesosAbreviados = new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    notation: "compact",
    maximumFractionDigits: 1,
  });
  const numeros = (valores) => valores.map(Number);

  Chart.defaults.font.family = "Inter, ui-sans-serif, system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = "#6b7280";
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
          borderColor: ROJO,
          backgroundColor: ROJO_SUAVE,
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: ROJO,
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
      datasets: [{ data: numeros(datos.medios.valores), backgroundColor: ROJO, borderRadius: 4, maxBarThickness: 28 }],
    },
    options: { indexAxis: "y", scales: { x: ejeEnPesos, y: ejeSinGrilla } },
  });

  dibujar("grafico-top", {
    type: "bar",
    data: {
      labels: datos.top.etiquetas,
      datasets: [{ data: numeros(datos.top.valores), backgroundColor: ROJO, borderRadius: 4, maxBarThickness: 28 }],
    },
    options: { indexAxis: "y", scales: { x: ejeEnPesos, y: ejeSinGrilla } },
  });
})();
