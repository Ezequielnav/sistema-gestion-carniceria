// Abre y cierra el menú lateral en celular y tablet.
document.addEventListener("DOMContentLoaded", () => {
  // Pestañas que se desplazan de costado (Reportes en el celular, RM-13): la elegida queda a la
  // vista. Solo mueve la barra de pestañas, no la página.
  for (const activa of document.querySelectorAll("nav.overflow-x-auto [aria-current=page]")) {
    const barra = activa.parentElement;
    const desde = activa.offsetLeft - barra.offsetLeft;
    barra.scrollLeft = desde - (barra.clientWidth - activa.offsetWidth) / 2;
  }

  const boton = document.querySelector("[data-menu-boton]");
  const menu = document.querySelector("[data-menu]");
  if (!boton || !menu) return;

  boton.addEventListener("click", () => {
    const abierto = boton.getAttribute("aria-expanded") === "true";
    boton.setAttribute("aria-expanded", String(!abierto));
    menu.classList.toggle("hidden", abierto);
  });
});
