# SPEC - H6 Integración, correcciones y cierre

**Estado:** aprobado (rama `h6`), con S-1 a S-5 como DEC-173 a DEC-177, S-7 a S-13 como DEC-178 a DEC-184 y S-6 como DEC-185 (09). Al aprobarlo se confirmó S-3 (mínimo y máximo de `stock_actual`); S-6 se aprobó después, ajustado (tabla final). **Etapas 1 a 5 implementadas** (CP-141 a CP-154; manual y guía en la etapa 5); etapa 6 con controles completos, revisión del diff y prueba integral (CP-151) y RM-13 hecho el 2026-11-08 con la guía de capacitación (OK después de corregir DF-06 a DF-08). Las decisiones de la etapa 0 ya están en 09 (DEC-159 a DEC-172).

Fuente de verdad: `/docs`. Este spec no agrega reglas del negocio. Toma las de CU-01, CU-04, CU-05, CU-07 y CU-08 (04), RF-39, RF-56, RF-57, RNF-02 a RNF-05 (03), RN-03 (04), DEC-159 a DEC-172 (09) y los recorridos RM-09 y RM-13 (08). PR-23 y PR-29 están cerradas como **supuestos del proyecto, no datos confirmados por el negocio** (DEC-170, DEC-171); si el negocio responde distinto, se registra una DEC nueva.

## 0. Módulos

| Módulo | Qué hace | Depende de |
|---|---|---|
| `correcciones` (L5, L6, L10, L11, L19) | Tope de líneas por venta, paginación de "Ventas de la caja", saldos del pago en una consulta, aviso de stock al retomar una venta y tope de stock con mensaje (DEC-162, DEC-164, DEC-165, DEC-169) | — |
| `cuenta-corriente` (L15 a L17) | Saldo acumulado en el estado de cuenta, comprobante del cobro y corrección de cobros y pagos con la caja cerrada (DEC-166 a DEC-168) | — |
| `navegador` (L2, L13) | Prueba del flujo de la venta con `pytest-playwright` (DEC-160) y buscador de productos común a la venta y al ingreso | `correcciones` (la prueba ya cubre el tope de líneas) |
| `celular` (L7, PR-23) | RM-09 a 375 px según DEC-170, con sus correcciones | `cuenta-corriente` (pantallas nuevas) |
| `manual` (RNF-04, PR-29) | Manual de usuario por rol y guía de la capacitación breve, con la contingencia sin internet (DEC-171) | Todo lo anterior (capturas del sistema terminado) |

Orden de construcción: `correcciones` → `cuenta-corriente` → `navegador` → `celular` → `manual` → cierre.

## 1. Objetivo

Dejar el sistema integrado y listo para la entrega: cerrar los pendientes de la lista L que quedaron para H6, probar de punta a punta la pantalla más usada, revisar el uso en el celular y entregar el manual de usuario con la capacitación breve.

**Usuarios:** cajera (venta, cobro, comprobante), Administrador (correcciones, estado de cuenta, pagos) y Dueños (Reportes en el celular).

### Ajustes del refactor de capas

| ID | Ajuste |
|---|---|
| R-1 | La corrección con la caja cerrada (DEC-166) usa las funciones públicas de caja que ya registran las reversas (`registrar_reversa_cobro` y `registrar_reversa_pago_proveedor`); la diferencia es que reciben la caja abierta en lugar de la de origen. `clientes` y `proveedores` siguen sin importar `ventas`, y `caja` sin importar `clientes` (DEC-131) |
| R-2 | El saldo acumulado y los saldos del comprobante salen de `clientes.services`, con el mismo cálculo que el saldo (DEC-21, DEC-111); no se guardan |
| R-3 | El tope de stock vive solo en `catalogo.services.mover_stock` (DEC-96); ningún otro módulo lo repite |
| R-4 | El buscador común de L13 es un componente propio sobre la lógica de `buscador.js`, como `elegir_cliente.js`; la venta y el ingreso lo usan sin cambiar su comportamiento |

### Reglas por módulo

| Módulo | Regla | Fuente | CP |
|---|---|---|---|
| **correcciones.** Una venta tiene a lo sumo 50 líneas, después de agrupar; el servidor rechaza más | DEC-162, DEC-53 | CP-141 |
| **correcciones.** "Ventas de la caja" pagina de a 25 | L6, DEC-86 | CP-142 |
| **correcciones.** Ningún movimiento deja `stock_actual` fuera del rango de la columna; se rechaza con mensaje | DEC-169, RI-07 | CP-143 |
| **correcciones.** El formulario de pago calcula los saldos con una cantidad fija de consultas | DEC-164 | CP-144 |
| **correcciones.** Al retomar una venta guardada, el aviso de stock usa el stock actual | DEC-165, DEC-46 | CP-145 |
| **cuenta-corriente.** El último saldo acumulado coincide con el saldo del cliente | DEC-168, DEC-21 | CP-146 |
| **cuenta-corriente.** El comprobante muestra saldo anterior y posterior al cobro | DEC-167 | CP-147 |
| **cuenta-corriente.** La cajera abre el comprobante al cobrar y reimprime los de la caja abierta de hoy; no ve el detalle del cobro ni el estado de cuenta | DEC-185, DEC-129 | CP-152 |
| **cuenta-corriente.** Un cobro o un pago con la caja cerrada se corrige con la reversa en la caja abierta; la caja cerrada no cambia; solo el Administrador, con motivo | DEC-166, RN-03 | CP-148, CP-149 |
| **navegador.** La venta funciona de punta a punta en Chromium: lector, buscador, suma en la misma línea y confirmación | DEC-160 | CP-150 |

### Criterios de aceptación

- La cajera no puede cargar la línea 51 de una venta y el servidor rechaza un envío con más de 50.
- "Ventas de la caja" pagina de a 25 y conserva la página al volver del detalle.
- Un ingreso que dejaría el stock por encima del máximo de la columna se rechaza con un mensaje, sin registrar nada.
- Al retomar una venta guardada, el aviso de stock de cada línea coincide con el stock actual.
- El estado de cuenta muestra el saldo después de cada movimiento y el último coincide con el saldo.
- Cada cobro tiene su comprobante imprimible con los datos de DEC-167; la cajera lo imprime al cobrar y reimprime los de la caja abierta de hoy, y el Administrador lo abre desde el detalle.
- El Administrador corrige un cobro y un pago cuya caja cerró: la reversa aparece en la caja abierta y en su cierre, y la caja cerrada sigue igual.
- La prueba de navegador de la venta pasa en local y en GitHub Actions.
- RM-09 sin fallas abiertas: consultas y reportes usables a 375 px y pantallas de operación sin desplazamiento horizontal.
- El manual de usuario cubre los tres roles y la contingencia sin internet.

**Fuera de H6:** despliegue y estáticos versionados (DEC-161, L3); modo sin conexión (DEC-171); carga de datos históricos (PR-28, RF-47, DEC-172); `movimiento_stock` (DEC-163); reportes automáticos (RF-46); pedidos a proveedores (PR-19).

## 2. Comandos

```
Pruebas:        .venv/bin/pytest
Navegador:      .venv/bin/playwright install chromium   (una vez por equipo; desde la etapa 3)
Pruebas de JS:  node --test apps/ventas/tests/js/*.cjs
Navegador:      .venv/bin/pytest -m navegador   (excluirlas: -m "not navegador")
Lint:           .venv/bin/ruff check . && .venv/bin/ruff format --check .
Chequeo:        .venv/bin/python manage.py check
Migraciones:    .venv/bin/python manage.py makemigrations --check --dry-run
Estilos:        npm run estilos
Servidor:       .venv/bin/python manage.py runserver 127.0.0.1:8000
```

## 3. Estructura

```
apps/ventas/services.py, views.py     tope de líneas (S-1), paginación de la caja (S-2), stock al retomar (S-4)
static/js/venta.js, venta_guardada.js tope en el formulario (S-1) y aviso al retomar (S-4)
apps/catalogo/services.py             tope de stock en mover_stock (S-3)
apps/proveedores/services.py          saldos de las deudas en una consulta con `deudas_para_pagar` (DEC-164); corrección del pago (S-7)
apps/clientes/services.py, views.py   saldo acumulado (S-5), comprobante (S-6), corrección del cobro (S-7)
templates/clientes/                   estado de cuenta con saldo acumulado y comprobante del cobro
apps/caja/                            reversas en la caja abierta (R-1) y su lugar en el cierre (S-8)
static/js/buscador_productos.js       buscador común de la venta y el ingreso (S-10, L13)
apps/ventas/tests/navegador/          prueba de navegador de la venta (S-9)
.github/workflows/pruebas.yml         instala Chromium para la prueba de navegador (S-9)
apps/comun/tests/test_flujo_h6.py     prueba integral (CP-151)
docs/manual-usuario.md, capacitacion.md  manual de usuario y guía de capacitación (S-12, ruta ajustada)
docs/                                 03, 04, 05, 06, 07, 08 y 09 al día
```

**Migraciones previstas:** ninguna. Las reversas ya tienen su referencia y su `UNIQUE` en `movimiento_caja` (05); los saldos se calculan al consultar (DEC-21). Si alguna resulta necesaria, se pide antes.

**Dependencia nueva (aprobada, DEC-160):** `pytest-playwright` con versión fija en `requirements.txt`, junto a `pytest` (el proyecto no separa las dependencias de desarrollo), y el Chromium que instala Playwright. Se agrega al llegar a la etapa 3.

## 4. Estilo de código

El mismo de H2 a H5: vistas finas con `requiere_funcion` y el control del servicio (permisos dobles), reglas en servicios, errores con `ValidationError` por campo, operaciones en `transaction.atomic()` con el orden de bloqueos de DEC-128 y docstrings que citan RF, RI y DEC. Dinero con `Decimal`.

## 5. Pruebas

- `pytest` con la base de prueba; nada toca la base de desarrollo.
- Cada decisión de H6 y del spec con al menos una prueba, por servicio y por pantalla (403 para quien no corresponde).
- Saldos con fechas fijas, anulaciones y saldo inicial; correcciones con la caja de origen cerrada, con la abierta de otro día y sin caja abierta; efectivo insuficiente en la reversa de un cobro.
- La cantidad de consultas del formulario de pago se verifica con `django_assert_num_queries`.
- CP nuevos propuestos: **CP-141** (tope de líneas), **CP-142** (paginación de "Ventas de la caja"), **CP-143** (tope de stock), **CP-144** (saldos del pago sin una consulta por ingreso), **CP-145** (aviso de stock al retomar), **CP-146** (saldo acumulado), **CP-147** (comprobante del cobro: datos y saldos), **CP-152** (comprobante del cobro: quién lo abre, DEC-185), **CP-148** (corrección de un cobro con la caja cerrada), **CP-149** (corrección de un pago con la caja cerrada), **CP-150** (prueba de navegador de la venta) y **CP-151** (prueba integral de H6). Se agregan a 08 al implementar cada etapa.
- Recorridos con Playwright en localhost con datos de ejemplo: RM-09 (celular) y RM-13 (flujo de H6).

## 6. Límites

- **Siempre:** trabajar en la rama `h6`; correr pruebas, lint, `check` y verificación de migraciones antes de commitear; actualizar `/docs` en el mismo cambio; dinero con `DecimalField` y `Decimal`; marcar como supuestos las DEC de H6 que lo son.
- **Preguntar antes:** cada migración; cualquier dependencia distinta de `pytest-playwright`; capturas del sistema dentro del repositorio (manual); cambiar una pantalla de operación más allá de lo que pida RM-09; ampliar el alcance a algo de "Fuera de H6".
- **Nunca:** leer `.env` ni datos reales; push o PR sin pedido; inventar reglas del negocio; presentar un supuesto como dato confirmado; modificar una caja cerrada; borrar operaciones.

## 7. Etapas

| Etapa | Alcance | CU / RF / DEC | CP |
|---|---|---|---|
| 0. Decisiones y spec | PR-23 y PR-29 cerradas como supuestos; lista L decidida; PR-28 fuera; docs al día; este borrador | DEC-159 a DEC-172 | — |
| 1. Correcciones chicas | L5 (servidor y formulario), L6, L19, L10 y L11 | CU-01, CU-05, CU-07; DEC-162, DEC-164, DEC-165, DEC-169; S-1 a S-4 | CP-141 a CP-145 |
| 2. Cuenta corriente y correcciones | L17, después L16 (usa el mismo cálculo de saldos) y L15 en cobros y pagos | CU-04, CU-07, CU-08; RF-39, RF-56, RF-57; DEC-166 a DEC-168, DEC-185; S-5 a S-8 | CP-146 a CP-149, CP-152 |
| 3. Navegador y buscadores | `pytest-playwright`, Chromium en GitHub Actions y la prueba de la venta (L2); con la prueba en verde, buscador común (L13) | CU-01, CU-05; DEC-160; S-9, S-10 | CP-150 |
| 4. Celular | RM-09 a 375 px con `catalogo/productos.html` (L7) y las correcciones que surjan | RNF-02, RNF-03; DEC-170; S-11 | — |
| 5. Manual y capacitación | Manual por rol, contingencia sin internet y guía de la capacitación breve | RNF-04; DEC-171; S-12 | — |
| 6. Cierre de H6 | Prueba integral (CP-151), RM-13, revisión, 07 y 08 al día y Pull Request | Todos los de H6 | Todos los de H6 |

## Decisiones del spec (DEC-173 a DEC-185)

| ID | Decisión | Por qué |
|---|---|---|
| S-1 | **Tope de líneas:** el formulario cuenta las líneas de la venta en curso (una por producto, DEC-53); con 50, agregar un producto nuevo no lo agrega y muestra "La venta llegó a 50 productos: confirmala y empezá otra"; sumar a una línea existente sigue funcionando. El servidor valida después de agrupar y rechaza con el mismo mensaje. El tope es una constante del servicio de ventas | DEC-162; el lector suma a la línea existente y no debe frenarse |
| S-2 | **"Ventas de la caja":** paginada de a 25, de la última a la primera, con la misma paginación de `comun/listados.py` | L6, mismo comportamiento que el historial (DEC-86) |
| S-3 | **Tope de stock:** `mover_stock` rechaza el movimiento que deja `stock_actual` por encima de 999.999.999,999 o por debajo de −999.999.999,999, con el mensaje "El stock de «producto» quedaría fuera del rango permitido", sin registrar nada. Dentro de ese rango el stock negativo de DEC-46 se mantiene | DEC-169; el límite inferior es el mismo problema de la columna. Aprobado con los dos límites |
| S-4 | **Stock al retomar:** una consulta de solo lectura (`/ventas/stock/?ids=...`, con los permisos de la pantalla de venta) devuelve el stock actual de los productos de la venta guardada; `venta_guardada.js` la pide al retomar y recalcula los avisos con `aviso_stock.js`. Si falla, la venta se retoma sin aviso de stock | DEC-165; el servidor no recibe stock del navegador |
| S-5 | **Saldo acumulado:** se calcula sobre todos los movimientos del cliente en orden de registro (fecha y hora, y luego id) y se muestra en la columna "Saldo" de cada fila; la pantalla sigue del más nuevo al más viejo y paginada de a 25, con el saldo correcto en cada página | DEC-168; calcularlo por página daría saldos falsos |
| S-6 | **Comprobante del cobro:** `/clientes/cobros/<id>/comprobante/`, con el formato del ticket (DEC-44) y los datos de DEC-167; un cobro anulado muestra "ANULADO" con la fecha. **Supuesto del proyecto.** El Administrador lo abre desde el detalle del cobro, de cualquier cobro. La cajera lo abre e imprime al terminar de registrar un cobro (la pantalla ofrece "Imprimir comprobante") y puede reimprimir los cobros que entraron a la caja abierta de hoy; los de una caja cerrada, de otro día o sin caja le dan 403. La cajera sigue sin ver el estado de cuenta (DEC-129) ni el detalle del cobro: solo el comprobante. Los dueños reciben 403 (DEC-134) | El cliente paga en el mostrador, donde cobra la cajera (DEC-110); mismo criterio que el ticket de la venta (DEC-84) |
| S-7 | **Corrección con la caja cerrada:** es la misma acción "Anular" del detalle del cobro o del pago. Si la caja de origen está cerrada, la pantalla avisa que la reversa va en la caja abierta (fecha y turno) y lo hace con el motivo; la caja abierta puede ser de otro día (criterio de DEC-72). Bloquea la caja abierta, el cobro o el pago y el cliente, en ese orden (DEC-128). Sin caja abierta, el mensaje lo dice y enlaza a Caja | DEC-166 sin una pantalla nueva |
| S-8 | **Cierre:** la pantalla y el reporte de cierre de la caja que recibe la reversa la listan con los demás cobros y pagos (DEC-127), con la fecha del cobro o del pago original | Explica la diferencia del turno que la registra |
| S-9 | **Prueba de navegador:** en `apps/ventas/tests/navegador/`, marcada `navegador`, con `live_server` y la base de prueba; en GitHub Actions se instala Chromium (`playwright install --with-deps chromium`); en local se saltea si falta el navegador, con el aviso de cómo instalarlo | DEC-160; misma regla que las pruebas de JavaScript sin Node |
| S-10 | **Buscador común (L13):** `static/js/buscador_productos.js`, usado por la venta y el ingreso; la prueba de navegador y las de JavaScript pasan antes y después sin cambios | Refactor sin cambio de comportamiento, con una prueba que lo respalda |
| S-11 | **RM-09:** a 375 px, como Administrador, cajera y dueño. Consultas y reportes: se leen sin desplazar la página de costado (las tablas se desplazan dentro de su recuadro, como DF-02). Operación (venta, caja, cobro, ingreso, pago): solo se verifica que no rompan la página. Cada falla es un DF en 08 | DEC-170 |
| S-12 | **Manual:** `docs/manual-usuario.md` (antes `docs/manual/manual-de-usuario.md`), una sección por rol (cajera, Administrador, dueños) con sus tareas paso a paso y la contingencia sin internet (DEC-171), y `docs/capacitacion.md` (antes `docs/manual/capacitacion.md`) con la guía de la capacitación breve (temas, orden y práctica con datos de ejemplo). Las capturas, si se suman, se piden antes (sección 6) | RNF-04; el informe final puede tomarlo de `/docs` |
| S-13 | **Datos de ejemplo:** se suman los casos que necesitan RM-09 y RM-13 (una caja cerrada con un cobro y un pago, y un cliente con varios movimientos), con datos ficticios | Que los recorridos no dependan de cargar datos a mano |

## Cambios al aprobar el spec

| Fecha | Cambio | Decisión |
|---|---|---|
| 2026-11-08 | S-3 aprobado con el mínimo y el máximo de `stock_actual`; el negativo de DEC-46 se mantiene dentro del rango | DEC-175 |
| 2026-11-08 | Etapa 3: las pruebas de navegador quedan en `tests/navegador/` de cada app (venta en `ventas`, cobro en `clientes` e ingreso en `proveedores`, este último como respaldo de L13). Inician sesión con el cliente de Django, sin escribir contraseñas, y corren al final de la corrida con `DJANGO_ALLOW_ASYNC_UNSAFE` activado solo para ellas (`pytest_runtest_setup` en `conftest.py`; en cualquier otra prueba se quita), porque el API síncrono de Playwright deja un bucle de eventos en el hilo de las pruebas hasta terminar la corrida (la aplicación no tiene código asíncrono). Chromium también se instala en GitHub Actions | DEC-180 |
| 2026-11-08 | Etapa 5: manual y guía en `docs/manual-usuario.md` y `docs/capacitacion.md`, a pedido del alumno; el CI verifica que el CSS versionado sea el compilado | DEC-183 |
| 2026-11-08 | Etapa 4: RM-09 automatizado (CP-154) en `apps/comun/tests/navegador/`, además de los recorridos; DF-05 corregido. Para que los listados de consulta "se usen bien" a 375 px, su columna principal lleva un ancho mínimo y la tabla se desplaza en su recuadro | DEC-182 |
| 2026-11-08 | Los reportes cuentan los cobros vigentes por su fecha y los cierres, el movimiento de caja, también después de una corrección de L15; nota en Ingresos y Totales por medio (CP-153) | DEC-186 |
| 2026-11-08 | S-6 aprobado después, ajustado: la cajera abre el comprobante al terminar el cobro y reimprime los de la caja abierta de hoy, sin ver el estado de cuenta ni el detalle del cobro; el Administrador, desde el detalle | DEC-185 |
