// Abre y cierra el menú lateral en celular y tablet.
document.addEventListener("DOMContentLoaded", () => {
  const boton = document.querySelector("[data-menu-boton]");
  const menu = document.querySelector("[data-menu]");
  if (!boton || !menu) return;

  boton.addEventListener("click", () => {
    const abierto = boton.getAttribute("aria-expanded") === "true";
    boton.setAttribute("aria-expanded", String(!abierto));
    menu.classList.toggle("hidden", abierto);
  });
});
