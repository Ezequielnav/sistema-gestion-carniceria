# SPEC - H7 Rediseño visual

**Estado:** aprobado (rama `h7`), con S-1 a S-13 como DEC-187 a DEC-199 (09). Al aprobarlo el alumno cambió S-1 (neutros cálidos), S-4 (logo provisorio del proyecto) y sumó S-13 (qué evitar); detalle en "Cambios al aprobar el spec". El logo y la paleta son **supuestos del proyecto, a validar con el dueño** (07, sección 8). **H7 terminado: etapas 1 a 5** (CP-155, RM-14). Lo que siga entra por rondas de ajuste (07, DEC-200).

Fuente de verdad: `/docs`. Este spec no agrega ni cambia reglas del negocio, funciones, URL ni textos funcionales: solo la apariencia. Toma RNF-01 a RNF-03 (03), DEC-07 (prototipos v0 como guía funcional), DEC-170 y DEC-182 (PC del mostrador con Chrome, celular para consultas y Reportes, RM-09 a 375 px), DEC-171 (contingencia sin internet) y el control del CI que compila los estilos (etapa 5 de H6). Reemplaza el estilo visual de DEC-30 (grises y rojo de Tailwind, Inter); el resto de DEC-30 (íconos Lucide, tarjetas del inicio) sigue.

## 0. Módulos

| Módulo | Qué hace | Depende de |
|---|---|---|
| `base` | Tokens de color y tipografía, fuentes propias, `base.html`, navegación, componentes comunes, inicio de sesión, 403 y favicon | — |
| `cajera` | Caja, venta, cobro y comprobantes impresos | `base` |
| `administrador` | Listados, formularios, bajas y detalles de productos, proveedores, ingresos, pagos, clientes, usuarios, medios de pago e historial | `base` |
| `reportes` | Reportes, Resumen con Chart.js e inicio del dueño, pensado también para el celular | `base` |

Orden de construcción: `base` → `cajera` → `administrador` → `reportes` → cierre.

## 1. Objetivo

Que el sistema se vea como la Carnicería Rojano y no como una plantilla genérica: la identidad sale del logo provisorio del proyecto, hecho por el alumno y a validar con el dueño (azul marino, blanco, ilustración de línea, serif de "ROJANO"), con una jerarquía pensada para lo que hace cada rol. Criterio general (S-13): funcional y profesional primero; la calidez sale de los colores, la tipografía y el logo, no de adornos.

**Usuarios:** la cajera en la PC del mostrador (operaciones rápidas, de pie, con lector), el Administrador en la PC (listados y formularios) y los dueños en Reportes, también desde el celular (DEC-170).

### Punto de partida

- Hoy el rojo de Tailwind marca **a la vez** las acciones principales (botones `bg-red-600`), los errores (`bg-red-50`, `text-red-700`) y la marca del menú: una anulación y un "Confirmar venta" se ven iguales. Es lo primero que corrige el rediseño (S-2).
- `base.html` carga Inter desde Google Fonts: sin internet la interfaz cae a la fuente del sistema. Las fuentes nuevas van en `static/vendor` (S-3), coherente con la contingencia de DEC-171.
- Los estilos se repiten como cadenas largas de clases en cada plantilla (por ejemplo, el botón principal aparece 19 veces con las mismas 9 clases) y cuatro archivos JS arman clases de color a mano (sección 8.3).

## 2. Plan de diseño

### 2.1 Paleta

Tomada del logo provisorio: el azul marino como color de la casa y de la acción, y neutros cálidos de papel y tinta (S-1) que le dan calidez sin adornos. El marino frío sobre papel cálido es el contraste que identifica al sistema; no hay un segundo acento. Contrastes calculados con la fórmula de WCAG 2.1.

| Token | Hex | Uso | Contraste |
|---|---|---|---|
| `marino-900` | `#0F2557` | Barra lateral, marca, encabezados de impresión | `superficie` encima: 14,4:1 |
| `marino-700` | `#1D3A7A` | Acción principal, enlaces, foco, pestaña elegida, serie de los gráficos | `superficie` encima y sobre `superficie`: 10,6:1; sobre `papel`: 9,6:1 |
| `marino-50` | `#ECEFF5` | Fondo de la opción elegida del menú y de la fila marcada del buscador | `marino-700` encima: 9,4:1; `tinta` encima: 14,7:1 |
| `papel` | `#F6F1E7` | Fondo de la página | — |
| `superficie` | `#FFFCF6` | Recuadros, tablas, formularios (blanco cálido, no crema) | — |
| `tinta` | `#211C17` | Texto principal y montos (casi negro cálido) | Sobre `superficie`: 16,5:1; sobre `papel`: 15,0:1 |
| `tinta-suave` | `#625A50` | Texto secundario, ayudas, encabezados de tabla | Sobre `superficie`: 6,6:1; sobre `papel`: 6,0:1 |
| `borde-campo` | `#7D7366` | Borde de campos y casillas (componente de interfaz, mínimo 3:1) | Sobre `superficie`: 4,5:1; sobre `papel`: 4,1:1 |
| `borde` | `#E3DACB` | Divisiones de tablas y recuadros (decorativo, no transmite información) | — |
| `menu-texto` | `#E3DACB` | Texto de la barra lateral | Sobre `marino-900`: 10,7:1 |
| `peligro` | `#B3261E` (fondo `#FBE9E4`) | Errores, anulaciones, bajas, diferencia de caja en contra | Sobre `superficie`: 6,4:1; sobre `papel`: 5,8:1; sobre su fondo: 5,6:1 |
| `alerta` | `#855000` (fondo `#FBEFD4`) | Stock bajo, deuda vencida, límite de cuenta corriente | Sobre su fondo: 5,9:1; sobre `superficie`: 6,5:1 |
| `exito` | `#1E6B45` (fondo `#E6F1E8`) | Caja abierta, operación registrada, activo | Sobre `superficie`: 6,3:1; sobre su fondo: 5,6:1 |

Todo texto cumple AA (4,5:1) y los bordes de campos superan 3:1 sobre los dos fondos. Sin modo oscuro (S-13). Los hex del marino se ajustan al archivo original del logo cuando esté en `static/img/logo/`, manteniendo estos contrastes.

### 2.2 Tipografía

- **Títulos y números protagonistas:** Barlow (OFL), en semibold, para el título de cada pantalla, los títulos de recuadros y los números que mandan en cada pantalla: el total de la venta, los montos de las tarjetas del inicio, el saldo del cliente al cobrar y las cifras del Resumen (clase `.cifra-grande`). Tiene carácter de cartel de comercio y separa con claridad el total del resto de los montos. Reemplaza a Source Serif 4 en este papel, que se percibía genérica (DEC-189).
- **Marca:** Source Serif 4 (OFL) queda solo para la marca "Rojano" y el encabezado de los comprobantes. Es el eco del serif de "ROJANO" sin imitar el logo: una serif de texto con tamaño óptico, que se lee bien a 20 px, a diferencia de una Didone de cartel.
- **Texto y controles:** Source Sans 3 (OFL). Sus cifras son tabulares por defecto y el cero no está tachado: fechas, horas y cantidades se alinean en columna y no se ven técnicas. Reemplaza a Atkinson Hyperlegible Next, la primera elección, cuyo cero tachado se veía como código (DEC-189).
- **Montos de tablas, listados y comprobantes:** Source Sans 3 con cifras tabulares (clase `.monto`): el precio unitario en peso normal, subtotales y totales en semibold. Fechas, horas y cantidades, también en Source Sans 3 con `.cifras`.
- **Escala** (1,25, base 16 px): 13 (notas y encabezados de tabla), 14 (tablas del Administrador), 16 (texto y campos), 20 (títulos de recuadro), 25 (título de pantalla), 31 (total de la venta y cifras del Resumen). Interlineado 1,5 en texto, 1,2 en títulos.
- Sin mayúsculas sostenidas en etiquetas ni encabezados de tabla (los prototipos v0 las usan; DEC-07 no obliga a copiarlas): oraciones normales, en tono `tinta-suave`.

Las tres fuentes van en `static/vendor/fuentes/` en `woff2`, subconjunto latino (con ñ, tildes, ¿, ¡ y º), con su licencia, declaradas con `@font-face` y `font-display: swap`. Barlow y Source Sans 3 tienen cifras tabulares y el cero sin tachar (verificado sobre los archivos).

### 2.3 Composición

**Marco común.** La barra lateral pasa a `marino-900` con el logo arriba: es el único lugar fuerte de la interfaz y el que dice "Rojano". El resto es silencioso: fondo `papel`, recuadros en `superficie` con borde fino y un solo radio chico (6 px) para campos y botones; los recuadros grandes no llevan sombra. Contenido alineado a la izquierda; los montos, a la derecha.

```
PC (cajera y Administrador)                       Celular (375 px)
┌──────────┬──────────────────────────────────┐   ┌───────────────────────┐
│ [logo]   │ Título de la pantalla (Barlow)   │   │ ☰  Título     [logo]  │
│ Rojano   │                    acción ppal.  │   ├───────────────────────┤
│──────────│──────────────────────────────────│   │ pestañas ‹ desliza ›  │
│ Inicio   │ filtros en una fila              │   │ tarjeta de cifra      │
│ Venta    │ ┌──────────────────────────────┐ │   │ tarjeta de cifra      │
│ Caja ●   │ │ tabla / formulario           │ │   │ gráfico               │
│ ...      │ └──────────────────────────────┘ │   │ tabla (se desliza en  │
│──────────│                                  │   │ su recuadro)          │
│ usuario  │                                  │   └───────────────────────┘
└──────────┴──────────────────────────────────┘
```

**Venta (cajera).** La pantalla más usada se diseña para la PC del mostrador a 1366 × 768 sin desplazar para confirmar (supuesto de diseño: no se conoce la resolución del mostrador; se verifica en el recorrido).

```
┌──────────────────────────────────┬────────────────────┐
│ Buscar o escanear  [__________]  │ Total              │
│                                  │ $ 12.345 (Barlow)  │
│ Producto      Cant.   Subtotal   │                    │
│ ───────────────────────────────  │ Medio de pago [v]  │
│ Asado         1,250   $ 9.999    │ Cliente (si CC)    │
│ ...                              │                    │
│                                  │ [ Confirmar venta ]│
└──────────────────────────────────┴────────────────────┘
```

### 2.4 Principios

1. **El marino es la casa y la acción; el rojo, solo lo que salió mal o no se puede deshacer.**
2. **Un solo lugar fuerte:** la barra lateral con el logo. Lo demás, quieto: sin sombras, sin degradados, sin íconos decorativos, sin animaciones de entrada, sin tarjetas iguales para todo (S-13).
3. **El color nunca va solo:** todo estado lleva también texto o signo (por ejemplo, "Anulada", "−$ 500,00", "Stock bajo"), como ya pide CP-154 para los textos visibles.
4. **Cada rol tiene su densidad** (S-6 a S-8): la cajera, controles grandes y pocos; el Administrador, tablas compactas; los dueños, cifras grandes y lectura en el celular.

### 2.5 Revisión del plan contra lo genérico

| Primera idea | Por qué se descartó | Qué queda |
|---|---|---|
| Inter con un acento de color de Tailwind (lo que hay) | Es el aspecto de cualquier panel; no dice nada de la carnicería | Marino del logo y Barlow para títulos y números protagonistas |
| Etiquetas en mayúsculas espaciadas, como en los prototipos v0 | Es el rasgo más repetido de las plantillas y cansa en formularios largos | Etiquetas en oración, en `tinta-suave` |
| Tarjetas con sombra para cada bloque | Corta la información en cajas iguales sin jerarquía | Recuadros solo donde agrupan; tablas y formularios sobre el fondo con borde fino |
| Grises fríos (primera versión del spec) | El alumno pidió neutros cálidos al aprobar (S-1). Para no caer en la fórmula de papel crema con serif y acento terracota, el único acento es el marino del logo, el blanco de los recuadros es apenas cálido y no hay tonos tierra | Papel y tinta cálidos con marino |
| Redibujar la vaca del logo como ícono | Sería una copia de baja calidad del logo | El archivo original del alumno en `static/img/logo/`; marcador tipográfico mientras no esté (S-4) |

## 3. Componentes

Se definen una vez en `@layer components` de `static/src/estilos.css` y reemplazan las cadenas repetidas de las plantillas. Los nombres siguen el estilo de los que ya existen (`.campo`, `.casilla`, `.cifras`).

| Componente | Variantes | Reemplaza |
|---|---|---|
| `.boton` | `-principal` (marino), `-secundario` (borde), `-peligro` (anular, dar de baja), `-discreto` (acciones de fila) | Las 4 cadenas de botón más repetidas (19, 17, 22 y 17 usos) |
| `.campo`, `.casilla`, `.etiqueta`, `.ayuda`, `.error-campo` | — | `mb-1.5 block text-sm …` (34 usos), `mt-1.5 text-xs …` (23), `mt-1.5 text-sm text-red-700` (26) |
| `.aviso` | `-error`, `-alerta`, `-exito`, `-info` | Mensajes de Django y recuadros `bg-red-50` / `bg-amber-50` (20 y 10 usos) |
| `.recuadro`, `.recuadro-tabla` | — | `mt-6 rounded-xl border …` (13) y `relative overflow-x-auto` (16; conserva `relative` por DF-02 y DF-05) |
| `.tabla` | `-compacta` (Administrador) | Encabezados y celdas de tabla (`px-5 py-3 …`, más de 150 usos) |
| `.pestanas` | — | `catalogo/_pestanas.html`, `proveedores/_pestanas.html`, la barra de Reportes |
| `.insignia` | `-exito`, `-alerta`, `-peligro`, `-neutra` | Estados (Activo, Inactivo, Anulada, Abierta, Cerrada, Pronto) |
| `.monto`, `.monto-negativo`, `.cifra-grande` | — | Montos de tablas en Source Sans 3 con cifras tabulares; números protagonistas en Barlow (`.cifra-grande`); los negativos con signo y color de `peligro` (DF-07) |
| `.opcion`, `.opcion-marcada` | — | Las filas que arman `buscador_productos.js` y `elegir_cliente.js` |

## 4. Comandos

```
npm run estilos                 # compila static/css/estilos.css (el CI falla si no coincide)
pytest -m "not navegador"       # pruebas de Python
pytest -m navegador             # CP-150 y CP-154 en Chromium
node --test apps/*/tests/js/    # pruebas de JavaScript
ruff check . && python manage.py check
```

## 5. Estructura

- `static/src/estilos.css`: tokens en `@theme` (colores y fuentes) y componentes en `@layer components`.
- `static/vendor/fuentes/`: las dos fuentes con su licencia.
- `static/img/logo/`: el archivo original del logo provisorio, que deja el alumno (S-4).
- `static/img/`: favicon (`favicon.svg`, `favicon-32.png`, `apple-touch-icon.png`) generado desde el logo.
- `templates/comun/_marca.html`: la marca, usada por la cabecera de `base.html`, el inicio de sesión y los comprobantes; muestra el logo si el archivo está y, si no, la marca tipográfica.
- `static/js/resumen.js`: los colores de los gráficos leídos de los tokens (S-11).

## 6. Pruebas

- Ninguna prueba se borra ni se debilita. Las pruebas que miran clases de diseño (sección 8.3) se actualizan a las clases nuevas manteniendo lo que protegen (S-12).
- CP-150 y CP-154 pasan sin cambios en sus selectores; CP-154 sigue siendo la verificación de RM-09.
- Cada etapa cierra con los cuatro comandos de la sección 4 y el CSS compilado sin diferencias.
- Recorrido manual de los tres roles al cierre, con capturas en carpetas ignoradas por git.

### Criterios de aceptación

- Ninguna pantalla cambia sus URL, campos, botones, mensajes ni el orden de sus pasos; los textos funcionales siguen iguales.
- Las acciones principales son marino y el rojo queda solo para errores, anulaciones, bajas y montos en contra.
- La interfaz no pide nada a internet: sin Google Fonts ni otra CDN.
- El logo aparece en la cabecera y en el inicio de sesión (o la marca tipográfica, si el archivo todavía no está).
- Todo texto cumple AA y los bordes de campos 3:1.
- La venta se confirma sin desplazar la página a 1366 × 768.
- RM-09 sin fallas a 375 px (CP-154) para los tres roles.
- El favicon, hecho desde el logo, aparece en la pestaña de Chrome.

## 7. Límites

- **Siempre:** cambiar solo plantillas, CSS, fuentes, imágenes y las clases que arman los JS de S-12; mantener `id`, `name`, `data-*`, `aria-*` y textos de los que dependen las pruebas (sección 8.3).
- **Preguntar antes:** cambiar el texto de un botón, etiqueta o mensaje, el orden de los campos o el contenido del menú; sumar información a una pantalla (por ejemplo, el estado de la caja en el encabezado).
- **Nunca:** cambiar vistas, servicios, formularios o URL; copiar el diseño visual de los prototipos v0 (DEC-07); cargar recursos de una CDN; sumar sombras en todo, bordes muy redondeados, degradados, íconos decorativos o librerías de interfaz nuevas (S-13).
- **Fuera de H7:** modo oscuro (S-13), la exportación a Excel y el panel de administración (S-10).

## 8. Inventario (etapa 0)

### 8.1 Plantillas por rol y pantalla (57)

Los roles salen del menú (`apps/comun/menu.py`) y de los permisos de cada vista. "Todos" incluye a los tres roles.

| Rol | Pantalla | Plantillas | Etapa |
|---|---|---|---|
| Todos | Marco, error de permisos e inicio de sesión | `base.html`, `403.html`, `usuarios/ingresar.html` | 1 |
| Todos | Piezas comunes | `comun/_icono.html`, `comun/_accesos.html`, `comun/_filtro.html` | 1 |
| Superusuario técnico | Panel (usuario del encabezado de Unfold) | `unfold/helpers/navigation_user.html` | Fuera (S-10) |
| Cajera | Inicio | `comun/inicio_cajera.html` | 1 |
| Cajera (y Administrador) | Caja: estado, apertura y cierre | `caja/caja.html`, `caja/cerrar.html` | 2 |
| Cajera, Administrador y dueños | Resumen de cierre imprimible | `caja/cierre.html` | 2 |
| Cajera (y Administrador) | Venta, ventas de la caja, detalle y ticket | `ventas/nueva.html`, `ventas/lista.html`, `ventas/detalle.html`, `ventas/ticket.html` | 2 |
| Cajera (y Administrador) | Cobro de cuenta corriente y comprobante | `clientes/cobrar.html`, `clientes/comprobante_cobro.html` | 2 |
| Administrador | Inicio | `comun/inicio.html` | 1 |
| Administrador (la cajera consulta en solo lectura) | Productos, categorías y ajustes de stock | `catalogo/_pestanas.html`, `catalogo/productos.html`, `catalogo/producto_form.html`, `catalogo/producto_baja.html`, `catalogo/categorias.html`, `catalogo/categoria_form.html`, `catalogo/categoria_baja.html`, `catalogo/ajustes.html` | 3 |
| Administrador | Clientes, estado de cuenta y detalle del cobro | `clientes/clientes.html`, `clientes/cliente_form.html`, `clientes/cliente_baja.html`, `clientes/estado_cuenta.html`, `clientes/cobro_detalle.html` | 3 |
| Administrador | Proveedores, ingresos y pagos | `proveedores/_pestanas.html`, `proveedores/proveedores.html`, `proveedores/proveedor_form.html`, `proveedores/proveedor_baja.html`, `proveedores/ingresos.html`, `proveedores/ingreso_nuevo.html`, `proveedores/ingreso_detalle.html`, `proveedores/pagos.html`, `proveedores/pago_form.html`, `proveedores/pago_detalle.html` | 3 |
| Administrador | Usuarios | `usuarios/usuarios.html`, `usuarios/usuario_form.html`, `usuarios/usuario_contrasena.html`, `usuarios/usuario_baja.html` | 3 |
| Administrador | Medios de pago e historial de ventas | `caja/medios.html`, `caja/medio_form.html`, `ventas/historial.html` | 3 |
| Dueños | Inicio | `comun/inicio_duenio.html` | 4 |
| Dueños y Administrador | Reportes | `reportes/_reporte.html`, `reportes/_sin_registros.html`, `reportes/resumen.html`, `reportes/ventas.html`, `reportes/productos.html`, `reportes/ingresos.html`, `reportes/medios.html`, `reportes/cierres.html` | 4 |

Totales: 7 comunes (con la del panel), 3 inicios, 5 de caja, 5 de ventas, 8 de catálogo, 7 de clientes, 10 de proveedores, 8 de reportes y 4 de usuarios. Tres no extienden `base.html` porque son para imprimir (`ventas/ticket.html`, `caja/cierre.html`, `clientes/comprobante_cobro.html`) y una es la de ingreso (`usuarios/ingresar.html`).

### 8.2 Componentes que se repiten

| Patrón | Dónde | Observación |
|---|---|---|
| Listado con tabla en recuadro, `sr-only` y paginación | 11 plantillas con paginación; 16 recuadros `relative overflow-x-auto` | `relative` es la corrección de DF-02 y DF-05: el componente la conserva |
| Formulario con etiqueta, ayuda y error por campo | Todos los `*_form.html`, `cobrar`, `cerrar`, `pago_form`, `ingreso_nuevo`, `usuario_contrasena` | Botonera `flex-col-reverse … sm:justify-end` (12 usos) |
| Confirmación de baja | `producto_baja`, `categoria_baja`, `cliente_baja`, `proveedor_baja`, `usuario_baja` | Mismo esquema: pasa a `.boton-peligro` |
| Pestañas | Catálogo, proveedores y Reportes | `menu.js` busca `nav.overflow-x-auto [aria-current=page]` (DF-08) |
| Filtro de fechas y proveedor | `comun/_filtro.html` en ajustes, ingresos y pagos; el de Reportes en `_reporte.html` | — |
| Tarjetas de cifras y accesos | Los tres inicios y el Resumen | `_accesos.html` compartido |
| Insignias de estado | 21 plantillas con `rounded-full` | Activo, Inactivo, Anulada, Abierta, Cerrada, Pronto |
| Aviso de error o alerta | 20 recuadros rojos y 10 ámbar | Hoy el rojo también es el de las acciones (sección 1) |
| Documento imprimible | Ticket, cierre de caja y comprobante del cobro | `print:` de Tailwind, botones `print:hidden` |
| Buscadores con lista | Venta, ingreso, cobro (`buscador_productos.js`, `elegir_cliente.js`) | Las filas las arma el JS (8.3) |

### 8.3 De qué dependen las pruebas

**Pruebas de navegador (CP-150, `apps/*/tests/navegador/`).** No miran clases de diseño, pero sí estos `id`, atributos y textos, que no cambian:

- `id`: `#buscar`, `#resultados`, `#lineas`, `#total`, `#confirmar`, `#errores`, `#alta-producto`, `#form-producto`, `#buscar-cliente`, `#clientes`, `#cliente-nombre`, `#cliente-saldo`, `#id_proveedor`, `#id_medio_pago`, `#menu-lateral`.
- Atributos: `[role=option]` en las listas, `[name=producto-nombre]`, `.aviso-stock` (clase con función: la usa `venta.js`), `nav[aria-label=Reportes] [aria-current=page]`.
- Textos (rol y nombre accesible): botones "Abrir menú", "Crear producto", "Ver productos", "Registrar cobro", "Imprimir"; enlaces "Productos", "Nuevo cobro", "Ir a Caja", "Comprobante del cobro N.º …"; etiquetas "Monto", "Medio de pago", "Ticket", "Comprobante de cobro", "Cantidad de …", "Precio de compra de …".

**CP-154 (`apps/comun/tests/navegador/test_celular.py`).** Recorre 36 pantallas del Administrador, 9 de la cajera y 8 de los dueños a 375 × 812 y revisa el estilo calculado, no las clases: que `scrollWidth` de la página no supere el ancho, que todo `a`, `button`, `input`, `select` y `textarea` visible quede dentro de la pantalla (salvo dentro de un contenedor con `overflow-x: auto` o `scroll`), que en las de consulta cada `table` tenga un ancestro con ese desplazamiento, que el menú abra con "Abrir menú" y que la pestaña elegida de Reportes quede a la vista. El rediseño tiene que respetar ese contrato: tablas dentro de un recuadro que se desplaza y nada fijo más ancho que 375 px.

**Pruebas de Python que miran el HTML.** Dependen de atributos con función (`id="buscar"`, `id="alta-producto"`, `id="ver-productos"`, `id="cobro"`, `data-producto`, `data-lineas-maximas`, `data-stock`, `data-cuenta-corriente`, `data-clientes`, `data-efectivo`, `name="producto-nombre"`), del menú (`<nav aria-label="Menú"`, `>Menú</p>`) y de **tres cadenas de clases de diseño** en `apps/ventas/tests/test_pantalla_ventas.py`: `id="venta" class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3"`, `class="min-w-0 space-y-4 lg:col-span-2" aria-label="Productos de la venta"` y `class="relative overflow-x-auto`. Protegen la corrección de DF-02 (S-12).

**JavaScript que arma clases de color.** `buscador_productos.js`, `elegir_cliente.js`, `venta.js` e `ingreso.js` escriben clases de Tailwind con colores (`bg-gray-100`, `text-red-700`, `hover:bg-red-50`, `text-amber-800`, entre otras) y `resumen.js` tiene el rojo de los gráficos fijo. `menu.js`, `cobro.js` y `sale_de_caja.js` solo alternan `hidden`. Las pruebas de JavaScript (`*.test.cjs`) no miran clases.

## 9. Etapas

| Etapa | Alcance |
|---|---|
| 0. Decisiones y spec | Este documento, el inventario y la planificación en 07 |
| 1. Base visual | Tokens, fuentes, `base.html`, navegación por rol, componentes, inicio de sesión, 403, inicios del Administrador y la cajera, favicon y marca |
| 2. Pantallas de la cajera | Caja, venta, ventas de la caja, cobro y los tres comprobantes |
| 3. Administrador | Productos, ingresos, pagos y proveedores, clientes, usuarios, medios de pago e historial |
| 4. Reportes y dueños | Reportes, Resumen con los gráficos, inicio del dueño y celular |
| 5. Cierre de H7 | Pruebas de navegador, RM-09 (CP-154), recorrido de los tres roles, revisión, docs (06, 08, 09, manual si cambian capturas o descripciones) y Pull Request |

## Decisiones del spec (DEC-187 a DEC-199)

Son decisiones de diseño del proyecto, no datos confirmados por el negocio. El logo, la paleta (S-1, S-4) y la resolución del mostrador (S-6) son además **supuestos del proyecto**, a validar con el dueño.

| ID | Decisión | Por qué |
|---|---|---|
| S-1 | **Paleta** de la sección 2.1: marino del logo (`#0F2557`, `#1D3A7A`), neutros cálidos de papel (`#F6F1E7`, `#FFFCF6`) y tinta casi negra cálida (`#211C17`), y tres colores de estado; todo texto AA y bordes de campos de 3:1 o más. Reemplaza los grises y el rojo de DEC-30. **Supuesto del proyecto**: provisoria hasta validarla con el dueño |  Identidad: el sistema se reconoce como el del negocio. Accesibilidad: todo texto cumple WCAG AA (4,5:1) y los bordes de campos 3:1, para leer bien en el mostrador con luz variable |
| S-2 | **Uso del color.** Acciones principales y enlaces: `marino-700`. Estados: `exito` (abierta, activo, registrado), `alerta` (stock bajo, deuda vencida, cerca del límite), `peligro` (errores, anular, dar de baja, montos en contra). Montos: `tinta` con cifras tabulares; los negativos llevan signo y `peligro`. El color nunca es la única señal |  Usabilidad: hoy el mismo rojo marca "Confirmar venta" y una anulación; separar acción (marino) de peligro (rojo) evita errores. Accesibilidad: con texto o signo además del color, se entiende sin distinguir colores (WCAG 1.4.1) |
| S-3 | **Tipografía.** Barlow semibold en títulos y en los números protagonistas (total de la venta, montos de las tarjetas del inicio, saldo del cliente al cobrar y cifras del Resumen); Source Sans 3 en el texto, los controles, fechas, horas, cantidades y los montos de tablas, listados y comprobantes, con cifras tabulares (precio unitario en peso normal, subtotales y totales en semibold); Source Serif 4 solo en la marca "Rojano" y el encabezado de los comprobantes. Escala de 2.2; las tres en `static/vendor/fuentes/` en `woff2`, sin CDN. Reemplaza a la primera versión (Atkinson Hyperlegible Next en el texto, por su cero tachado, y Source Serif 4 en títulos y montos) | Devolución de un compañero: la serif en los títulos se percibía genérica. Barlow tiene carácter de cartel de comercio y marca una jerarquía clara entre el total y el resto de los montos, que en las tablas quedan en Source Sans 3. Uso real: la cajera lee montos, horas y cantidades de un vistazo; las dos tienen cifras tabulares (alineadas en columna) y el cero sin tachar, que se leen como datos del negocio y no como código. Fuentes propias: la interfaz se ve igual sin internet (DEC-171) |
| S-4 | **Logo y favicon.** El logo de los prototipos es el **logo provisorio del proyecto**, hecho por el alumno (**supuesto del proyecto, a validar con el dueño**, no un dato del negocio). Su archivo original va en `static/img/logo/` y se usa en la cabecera y en el inicio de sesión, desde `comun/_marca.html`; el favicon sale del logo. Mientras el archivo no esté, la marca es tipográfica ("Carnicería" chico y "Rojano" en Source Serif 4, sobre marino); no se recorta el PNG de los prototipos |  Identidad con el archivo original, no con una copia de baja resolución; al estar en un solo lugar, si el dueño lo cambia no se tocan las pantallas |
| S-5 | **Navegación por rol.** El menú mantiene funciones, nombres, orden (`menu.py`) y el rótulo "Menú"; cambia la apariencia: barra lateral marino y la opción actual con `aria-current`; en el celular, el mismo botón "Abrir menú". No se suma información nueva |  Usabilidad: cada rol ve solo lo suyo y sabe dónde está. Accesibilidad: `aria-current` anuncia la pantalla actual a los lectores de pantalla, no solo con color (hoy solo se marca "Inicio") |
| S-6 | **Cajera (PC con Chrome).** Controles de 44 px de alto como mínimo, texto de 16 px, venta en dos columnas con el total en Barlow de 31 px y "Confirmar venta" a la vista a 1366 × 768 (**supuesto del proyecto**, se verifica en el recorrido), foco visible marino de 2 px. Caja y cobro: el dato que se cuenta o se cobra, grande |  Uso real: la cajera trabaja de pie, con apuro, teclado y lector (DEC-170); controles de 44 px, total grande y confirmar sin desplazar acortan cada venta. El foco visible sirve a quien usa solo el teclado (WCAG 2.4.7) |
| S-7 | **Administrador (PC).** Tablas compactas (filas de 40 px, texto de 14 px), filtros en una fila, acción principal arriba a la derecha, formularios en una columna de hasta 640 px agrupados por tema y bajas con `.boton-peligro` |  Uso real: el Administrador revisa listados largos y carga formularios en la PC; más filas a la vista y formularios en una columna se recorren más rápido y con menos errores |
| S-8 | **Dueños (Reportes, también en el celular).** Cifras del Resumen en Barlow grande, una tarjeta por cifra en una columna en el celular, pestañas que se deslizan con la elegida a la vista (DF-08) y tablas que se desplazan en su recuadro; en la PC, en grilla |  Uso real: los dueños consultan desde el celular (DEC-170); una cifra por tarjeta y tablas que se desplazan en su recuadro se leen a 375 px sin zoom (RM-09) |
| S-9 | **Comprobantes impresos** (ticket, cierre de caja y comprobante del cobro): entran, pensados para blanco y negro: logo o marca en negro, Source Serif 4 en el encabezado, sin fondos de color, mismo contenido y mismo ancho |  Uso real: se imprimen en impresoras comunes y en blanco y negro; sin fondos de color se leen bien y no gastan tinta, con la misma identidad que la pantalla |
| S-10 | **Exportaciones y panel.** PDF de reportes: solo el encabezado (nombre del negocio y una línea `marino-900`, con las fuentes estándar de PDF). Excel: sin cambios. Panel de administración (Unfold, solo el superusuario técnico, DEC-150): fuera de H7 |  Alcance: los dueños reciben el PDF y lo reconocen como del negocio; Excel es para trabajar los datos y el panel lo usa solo el superusuario técnico, así que no suman valor y sí trabajo |
| S-11 | **Gráficos de Chart.js** con la paleta nueva: serie en `marino-700`, relleno de la línea al 8 %, grilla `borde` y textos `tinta-suave`, leídos de las variables CSS en `resumen.js` en lugar de los hex fijos. Una sola serie por gráfico: sin paleta categórica |  Coherencia: los gráficos usan los colores del sistema; tomarlos de las variables CSS deja un solo lugar para cambiarlos si cambia la paleta |
| S-12 | **Clases en JS y pruebas que miran clases.** Las filas que arman `buscador_productos.js`, `elegir_cliente.js`, `venta.js` e `ingreso.js` usan los componentes nuevos (`.opcion`, `.opcion-marcada`, `.boton-discreto`, `.aviso-stock` con su función intacta), sin cambiar su comportamiento. Las tres aserciones de clases de `test_pantalla_ventas.py` se actualizan a las clases nuevas manteniendo lo que protegen (DF-02) |  Mantenimiento: los colores viven en el CSS y no repartidos en el JS. Calidad: las pruebas siguen protegiendo lo mismo (DF-02), con otras clases |
| S-13 | **Qué evitar.** Sombras en todo, bordes muy redondeados, degradados, íconos decorativos (los de Lucide quedan donde identifican una función), modo oscuro y librerías de interfaz nuevas. Solo cambian plantillas, CSS y los JS de S-12, sin cambios de comportamiento ni de textos funcionales. Criterio general: funcional y profesional primero; la calidez sale de los colores, la tipografía y el logo, no de adornos |  Profesionalidad: un sistema de trabajo se juzga por lo claro y rápido que es, no por los adornos; sin librerías nuevas no suma dependencias ni riesgo, y sin cambiar comportamiento ni textos las pruebas y el manual siguen valiendo |

## Cambios al aprobar el spec

| Fecha | Cambio | Decisión |
|---|---|---|
| 2026-11-08 | S-1: neutros cálidos (papel y tinta casi negra cálida) en lugar de grises fríos; el marino se mantiene; contrastes AA recalculados | DEC-187 |
| 2026-11-08 | S-4: el logo de los prototipos es el logo provisorio del proyecto, hecho por el alumno, a validar con el dueño; el archivo original va en `static/img/logo/`, se usa en la cabecera y el inicio de sesión y de él sale el favicon; la marca tipográfica queda como marcador | DEC-190 |
| 2026-11-08 | S-13 nueva: qué evitar y criterio general | DEC-199 |
| 2026-11-09 | Etapa 1: S-4 y S-5 necesitan saber si el archivo del logo está y qué opción del menú corresponde a la pantalla (también en las internas); lo resuelve el procesador de contexto de `comun`, sin cambiar vistas ni permisos (precisión de S-13 en DEC-199). Los grises de Tailwind y el blanco se redefinen a los neutros cálidos para que las pantallas de las etapas 2 a 4 no queden en gris frío mientras tanto. Atkinson Hyperlegible Next tiene cifras tabulares: no hace falta la alternativa de S-3 | DEC-189 a DEC-191 |
| 2026-11-09 | Ajustes de la etapa 1 pedidos por el alumno: un ícono de Lucide propio por función del menú (`icono` en `menu.py`), el mismo en los accesos del inicio; los montos en Source Serif 4 con la clase `.monto`, porque el cero de Atkinson Hyperlegible Next está tachado; "Registrar venta" como acción principal del inicio de la cajera; a 375 px, "Últimas ventas" oculta el medio de pago para que el total quede a la vista; Inicio dentro del grupo "Menú" | DEC-199 |
| 2026-11-09 | S-3: texto y controles en Source Sans 3 en lugar de Atkinson Hyperlegible Next, mismo par que Source Serif 4, con cifras tabulares y el cero sin tachar en fechas, horas y cantidades | DEC-189 |
| 2026-11-09 | Etapa 2: se suma Source Serif 4 en 400 para los montos de las tablas, que no van en negrita; los comprobantes usan el componente `.hoja` (en pantalla, hoja con borde; al imprimir, sin fondo ni borde y en negro); la aserción de DF-02 en `test_pantalla_ventas.py` mira `.recuadro-tabla` en la plantilla y que su regla en `estilos.css` aplique `relative overflow-x-auto`; las otras dos aserciones de clases no cambiaron porque la grilla de la venta se mantuvo | DEC-195, DEC-198 |
| 2026-11-09 | Tipografía C, elegida por el alumno entre tres opciones comparadas en capturas: Barlow semibold en títulos y números protagonistas, Source Sans 3 en el texto y los montos de tablas (precio unitario normal, subtotal semibold), Source Serif 4 solo en la marca y el encabezado de los comprobantes; se quita Source Serif 4 en 400, que ya no se usa | DEC-189 |
| 2026-11-09 | Etapa 3: todas las anulaciones y bajas usan `.boton-peligro` (rojo lleno), igual que "Anular venta" de la etapa 2, en lugar del botón rojo con borde que tenían algunas; los íconos decorativos de los listados vacíos se quitan (S-13); un `.campo` seguido de su `.error-campo` lleva el borde en `peligro`; la insignia "Efectivo" de los medios de pago pasa a neutra, porque el verde queda para estados | DEC-188, DEC-193, DEC-199 |
| 2026-11-09 | Ajustes de la etapa 3 y etapa 4: en el celular, las tablas de consulta dejan a la vista lo que importa y ocultan el detalle desde 640 px hacia abajo (productos: plus y categoría; estado de cuenta: fecha completa y detalle; reportes: fecha larga y columnas parciales, quedan el total y la diferencia de caja); el dato oculto sigue en la pantalla de PC, el Excel y el PDF. El Resumen usa `.cifra-grande` y los gráficos leen `--color-marino-700`, `--color-borde` y `--color-tinta-suave`. El PDF usa Times-Bold en marino para el nombre del negocio y una línea marino debajo, sin incrustar fuentes | DEC-194, DEC-196, DEC-197 |
| 2026-11-09 | Ajuste de la etapa 4, pedido por el alumno: "Ventas diarias" agrupada por día en pantalla y en el PDF (`tabla_ventas_pdf`): el día con sus ventas y su total en semibold, los turnos debajo con sangría solo si el día tiene más de uno, el turno único al lado de la fecha y el total del rango separado con una línea; sin fondo alternado. En la PC, "Ventas diarias" e "Ingresos por día" tienen ancho máximo; en el PDF, todas las tablas van al ancho de la hoja, con encabezados que pasan a dos renglones y fechas con el día de la semana. El Excel sigue con la tabla de antes, para trabajar los datos; los cálculos no cambian | DEC-140, DEC-196 |
| 2026-11-09 | Etapa 5 (cierre), con ajustes del alumno: la barra lateral ocupa todo el alto de la página; cada reporte fija el ancho de toda su tarjeta; en Ingresos por día los ceros van atenuados (`tinta-tenue`, 4,9:1) en pantalla y en gris en el PDF, y "Fuera de caja" en cero en todo el rango no compite; los días de la semana llevan tilde (filtro `con_dia`, también en el PDF); el cierre de caja en el celular muestra cada medio en bloque, con la diferencia a la vista, y se imprime igual que antes; medios de pago aclara "No se desactiva" en el efectivo en lugar de repetir su nombre; el botón Filtrar a su tamaño | DEC-188, DEC-194, DEC-195 |

## Preguntas pendientes

- Validar con el dueño el logo y la paleta provisorios (07, sección 8). Si cambian, se registra una DEC nueva.
- Resolución de la pantalla del mostrador: se asume 1366 × 768 (S-6) y se verifica en el recorrido.
