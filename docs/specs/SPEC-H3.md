# SPEC - H3 Stock y proveedores (CU-13, CU-05, CU-07, CU-06)

**Estado:** aprobado (R-1 a R-9 como DEC-96; S-1 a S-9 como DEC-87 a DEC-95).

Fuente de verdad: `/docs`. Este spec no agrega reglas del negocio. Toma las de CU-05, CU-06, CU-07 y CU-13 (04), RF-22 a RF-26 y RF-29 a RF-33 (03), RN-08 a RN-10 (04), RI-07, RI-08, RI-09, RI-12, RI-13, RI-14 y RI-16 (05), DEC-78 a DEC-86 (09) y los casos CP-30 a CP-37 y CP-90 a CP-93 (08). Las preguntas de H3 (PR-03, PR-17, PR-18, PR-20) están cerradas como **supuestos del proyecto, no datos confirmados por el negocio** (DEC-78). Lo que `/docs` no fijaba está en la sección final (S-1 a S-9, DEC-87 a DEC-95), y los ajustes del refactor, en R-1 a R-9 (DEC-96), igual que en los specs de H2. Como ellos, este spec vive en `docs/specs/`, se versiona con el código, se cita desde 04 en la implementación de cada caso de uso y, si cambia después de aprobado, se anota en "Cambios después de aprobar el spec".

## 0. Módulos

| Módulo | Qué hace | Depende de |
|---|---|---|
| `stock` | Servicio único de stock y de cantidades en catálogo; ventas, anulación de ventas, ingreso y su anulación lo usan (R-1, R-2) | — |
| `proveedores` (CU-13) | Alta, modificación, baja lógica y reactivación de proveedores | — |
| `ingreso` (CU-05) | Ingreso de mercadería con condición de pago, stock y precio de compra; anulación sin pagos | `stock`, `proveedores`; para `CONTADO`, `pago` |
| `pago` (CU-07) | Pago a proveedor de un ingreso con saldo; egreso de caja si es en efectivo; anulación con reversa | `proveedores`, caja (función pública, R-3) |
| `consulta-stock` (CU-06) | Consulta de stock con filtros y alertas de stock mínimo; tarjeta "stock bajo" del inicio | `stock` (en catálogo, sin depender de `proveedores`, R-7) |

Dirección de dependencias (R-6): `proveedores` usa `catalogo` y `caja`; `catalogo` y `caja` nunca importan `proveedores`.

Orden de construcción: `stock` → `proveedores` → `ingreso` a crédito y su anulación → `pago`, su anulación e `ingreso` `CONTADO` → `consulta-stock`. El contado registra su pago con el servicio de CU-07 (DEC-81), por eso se cierra junto con `pago`.

## 1. Objetivo

El Administrador registra a los proveedores, carga la mercadería que entra (sube el stock y deja una deuda o un pago), paga esas deudas en efectivo (desde la caja abierta) o por transferencia, anula con reversa un ingreso o un pago cargado por error, y consulta el stock con alertas de stock mínimo. Antes, el código de stock y de caja se ordena para que ventas, ingresos y pagos usen las mismas funciones.

**Usuario:** el rol Administrador (matriz de actores de 04). La cajera y los dueños no acceden a estas pantallas (CU-06 para ellos sigue a confirmar: PR-25).

### Ajustes del refactor de capas

No están escritos en `/docs`: salen de revisar el código que H3 va a tocar.

| ID | Ajuste | Etapa |
|---|---|---|
| R-1 | `catalogo.services.mover_stock(producto, cantidad)` es el único punto que cambia `stock_actual`: aplica RI-07 (solo productos con control de stock), actualiza con `F()` y admite negativo (DEC-46). Hoy la venta y la anulación lo hacen por su cuenta en `ventas/services.py` | 1 |
| R-2 | La regla de cantidades por unidad (RI-16, DEC-48) pasa a `catalogo.services.validar_cantidad(producto, cantidad)`. El tope de DEC-76 queda solo en ventas, que lo suma aparte; el ingreso no lo usa (DEC-79, DEC-81) | 1 |
| R-3 | `caja.services` expone funciones públicas para el egreso de un pago a proveedor y su reversa (`ANULACION_PAGO`), que comparten con el egreso "otro" el bloqueo de la caja y el control de efectivo. Hoy `_caja_abierta_bloqueada` y `_esperado` son privados y el egreso "otro" es solo de la cajera | 4 |
| R-4 | `proveedores.services` concentra saldo derivado (DEC-21), RI-08 y RI-14. El modelo ya dice que RI-14 "se valida en el servicio" y el servicio está vacío | 3 y 4 |
| R-5 | Los docstrings "A confirmar (PR-03)" de `UnidadMedida` y "(PR-18)" de `CondicionPago` citan DEC-79 y DEC-81 | 1 |
| R-6 | `proveedores` depende de `catalogo` y `caja`, nunca al revés: catálogo y caja no importan nada de `proveedores`. Una prueba de estructura lo verifica | 2 a 5 |
| R-7 | CU-06 vive en catálogo. El filtro por proveedor usa la relación inversa de `producto_proveedor` en el servicio de catálogo, sin importar servicios de `proveedores` | 5 |
| R-8 | Las alertas de stock mínimo (DEC-82) se calculan en una sola función del servicio de catálogo, que usan la consulta de stock y la tarjeta del inicio; la plantilla solo muestra el resultado | 5 |
| R-9 | Las pantallas nuevas siguen el patrón de H2: `requiere_funcion` con la función del menú, control de permisos también en el servicio (permisos dobles) y el menú como única tabla de permisos. Las reglas no se repiten en vistas ni plantillas | 2 a 5 |

### Reglas por módulo

| Regla | Origen |
|---|---|
| **stock.** Ventas, anulación de ventas, ingreso y anulación de ingreso cambian el stock solo con `mover_stock`; un producto sin control de stock no cambia. El comportamiento de ventas y anulación de ventas no cambia | RI-07, DEC-46, DEC-70, R-1 |
| **stock.** `validar_cantidad`: mayor a 0, entera por `UNIDAD`, hasta 3 decimales por `KG`. Solo la venta rechaza además más de 100 por línea | RI-16, DEC-48, DEC-76, DEC-79, R-2 |
| **proveedores.** Nombre obligatorio; teléfono y email opcionales; baja lógica; un proveedor dado de baja no recibe ingresos ni pagos y se reactiva desde la pantalla | RF-29, RI-11, S-1 |
| **ingreso.** Proveedor activo, al menos una línea, productos activos, cantidad según `validar_cantidad` y precio unitario mayor o igual a 0; el total es la suma de los subtotales redondeados (como DEC-49). La fecha es la de hoy y no se edita | RF-22, RI-12, RI-16, DEC-79, S-3, S-7 |
| **ingreso.** Al confirmar, en una operación: ingreso, detalles, stock (`mover_stock`) y precio de compra en `producto_proveedor` | RF-23, RNF-10, S-4 |
| **ingreso.** `A_CREDITO` deja la deuda por el total. `CONTADO` pide el medio (efectivo o transferencia) y registra el pago por el total con el servicio de CU-07; si el pago se rechaza, no se guarda nada | RF-30, RN-08, DEC-80, DEC-81, CP-92 |
| **ingreso.** Remito o factura (y su fecha, si hace falta) en `observacion`, texto libre. El tope de la venta (DEC-76) no aplica | DEC-81, CP-93, S-7 |
| **ingreso.** Alta de producto nuevo desde el ingreso con el servicio de CU-11 (A1) | RF-24, S-5 |
| **ingreso.** Anulación con motivo, solo el Administrador, si el ingreso no tiene pagos vigentes (un contado se anula después de anular su pago). Devuelve el stock con `mover_stock`; puede quedar negativo. No se edita: se anula y se carga de nuevo | S-6 |
| **pago.** Se elige un ingreso vigente del proveedor con saldo; monto mayor a 0 y no mayor al saldo del ingreso. Los pagos anulados no cuentan para el saldo | RF-31, RF-32, RI-08, RI-14, CU-07 A2, DEC-81 |
| **pago.** Medios: efectivo o transferencia, tanto en el pago de un ingreso a crédito como en el contado. Efectivo: caja abierta del día, egreso `PAGO_PROVEEDOR` en la misma operación a nombre de quien registra; si supera el efectivo esperado, se rechaza mostrando el máximo. Transferencia: sin movimiento de caja | RF-33, RN-09, RI-09, RI-13, DEC-80, CP-36, CP-90, CP-91 |
| **pago.** Anulación con motivo, solo el Administrador: por transferencia, siempre; en efectivo, solo si la caja de su egreso sigue abierta, con una reversa `INGRESO` de concepto `ANULACION_PAGO` en esa caja, vinculada al pago, a nombre de quien anula y con el motivo; el egreso original no se toca. El saldo del ingreso vuelve a subir | S-6 |
| **consulta-stock.** Lista de productos activos con control de stock, con filtros por categoría, proveedor y "solo con alerta"; alerta si `stock_actual <= stock_minimo` o, sin mínimo, si `stock_actual <= 0` (DEC-101); la carne no aparece | RF-25, RF-26, RN-10, DEC-82, CP-37, R-7, R-8 |
| **consulta-stock.** La tarjeta "stock bajo" del inicio cuenta los productos con alerta y la ve solo el Administrador | DEC-30, DEC-82, R-8 |

**Fuera de H3:** vencimientos (RF-28, PR-21), pedidos a proveedor (RF-34, PR-19), registro de faltantes (RF-27, PR-37), edición de ingresos y pagos (se anulan y se cargan de nuevo, S-6), datos de contacto extra (PR-31), CU-06 para la cajera y los dueños (PR-25).

### Criterios de aceptación

1. Con R-1 y R-2, las pruebas de ventas y anulación de ventas (CP-12, CP-13, CP-83, CP-85, CP-87) pasan sin cambios en sus resultados.
2. El Administrador da de alta, modifica, da de baja y reactiva un proveedor; la cajera y los dueños reciben 403 (CP-99).
3. Un ingreso `A_CREDITO` de 2 aceites a $ 1.000 sube el stock en 2, guarda el precio en el detalle y en `producto_proveedor`, y deja un saldo de $ 2.000 (CP-30, CP-31, CP-32, CP-100).
4. Un ingreso con 1,5 unidades se rechaza; 150 kg de un producto por kg se acepta (CP-93).
5. Anular ese ingreso sin pagos devuelve el stock (aunque quede negativo) y el saldo vuelve a 0; con un pago vigente, se rechaza (CP-101).
6. Un pago de $ 500 por transferencia baja el saldo a $ 1.500 sin movimiento de caja; uno en efectivo crea el egreso `PAGO_PROVEEDOR` y, si supera el efectivo esperado, se rechaza mostrando el máximo (CP-33, CP-36, CP-90).
7. Un pago mayor al saldo del ingreso o de un ingreso de otro proveedor se rechaza (CP-34, CP-35).
8. Sin caja abierta, o con la de otro día, un pago en efectivo se rechaza (CP-91).
9. Un ingreso `CONTADO` en efectivo sin efectivo suficiente no deja ingreso, stock, pago ni egreso (CP-92).
10. Anular un pago por transferencia sube el saldo; uno en efectivo con su caja abierta deja una reversa en la caja; con la caja cerrada, se rechaza (CP-102).
11. La consulta de stock marca los productos en o por debajo del mínimo y, sin mínimo, los que tienen 0 o menos (DEC-101), filtra por categoría y proveedor, y el inicio del Administrador muestra la tarjeta "stock bajo" (CP-37).

## 2. Comandos

```
Pruebas:        .venv/bin/pytest
Pruebas de JS:  node --test apps/ventas/tests/js/*.cjs
Lint:           .venv/bin/ruff check . && .venv/bin/ruff format --check .
Chequeo:        .venv/bin/python manage.py check
Migraciones:    .venv/bin/python manage.py makemigrations --check --dry-run
Estilos:        npm run estilos
Servidor:       .venv/bin/python manage.py runserver 127.0.0.1:8000
```

## 3. Estructura

```
apps/catalogo/services.py        mover_stock, validar_cantidad, consulta de stock y alertas (R-1, R-2, R-7, R-8)
apps/catalogo/views.py, urls.py  consulta de stock (CU-06)
apps/caja/services.py            egreso de pago a proveedor y su reversa (R-3)
apps/proveedores/services.py     proveedores, ingresos, pagos, anulaciones y saldo (R-4)
apps/proveedores/forms.py        formularios de proveedor, ingreso, pago y anulación
apps/proveedores/views.py, urls.py  CU-13, CU-05 y CU-07
apps/ventas/services.py          usa mover_stock y validar_cantidad (sin cambiar comportamiento)
templates/proveedores/           pantallas de CU-13, CU-05 y CU-07
templates/catalogo/stock.html    pantalla de CU-06
apps/*/tests/                    pruebas por módulo; prueba de estructura para R-6
docs/                            01, 03, 04, 05, 06, 07, 08 y 09 al día
```

**Migraciones previstas (se piden al llegar a cada etapa):** la anulación (S-6) necesita un estado en `ingreso_mercaderia` y en `pago_proveedor` con fecha, usuario y motivo de la anulación (como DEC-67), y el concepto `ANULACION_PAGO` en `movimiento_caja` (RI-13: lleva el pago; siempre es un ingreso) con una restricción de una sola reversa por pago. El resto del modelo ya existe desde H1.

## 4. Estilo de código

El mismo de H2: vistas finas con `requiere_funcion` y el control del servicio (permisos dobles), reglas en servicios, errores con `ValidationError` por campo, operaciones en `transaction.atomic()` con `select_for_update` donde hay concurrencia, y docstrings que citan RF, RI y DEC.

```python
def mover_stock(producto, cantidad):
    """Suma o resta `cantidad` al stock si el producto lo controla (RI-07).

    Única forma de cambiar stock_actual (R-1). Puede quedar negativo (DEC-46).
    """
    if not producto.controla_stock:
        return
    Producto.objects.filter(pk=producto.pk).update(stock_actual=F("stock_actual") + cantidad)
```

## 5. Pruebas

- `pytest` con la base de prueba; nada toca la base de desarrollo.
- Cada regla RN y RI de H3 y cada decisión del spec con al menos una prueba, por servicio y por pantalla (permisos con 403).
- Prueba de estructura: `catalogo` y `caja` no importan `proveedores` (R-6).
- Concurrencia: un pago en efectivo, o su anulación, y el cierre de caja al mismo tiempo, como CP-88.
- CP nuevos propuestos: **CP-99** (gestión de proveedores), **CP-100** (precio de compra sugerido y actualizado), **CP-101** (anulación de ingreso) y **CP-102** (anulación de pago). Los demás ya existen en 08.
- Recorrido manual en localhost con datos de ejemplo al cerrar cada etapa con pantalla, y un RM de H3 en el cierre.

## 6. Límites

- **Siempre:** trabajar en la rama `h3`; correr pruebas, lint, `check` y verificación de migraciones antes de commitear; actualizar `/docs` en el mismo cambio; dinero con `DecimalField`; marcar las DEC de H3 como supuestos del proyecto.
- **Preguntar antes:** cada migración; dependencias nuevas; cambiar el comportamiento de ventas, anulación de ventas o cierre de caja; ampliar el alcance a algo de "Fuera de H3".
- **Nunca:** leer `.env` ni datos reales; push o PR sin pedido; inventar reglas del negocio (lo que falte va como pregunta y DEC); presentar un supuesto como dato confirmado; borrar ingresos, pagos o movimientos de caja.

## Decisiones del spec (DEC-87 a DEC-95)

| ID | Decisión | Por qué |
|---|---|---|
| S-1 | CU-13 igual que CU-11: listado de activos con "Incluir dados de baja", alta, modificación, baja con confirmación y "Reactivar" (como DEC-85). El nombre repetido no se bloquea | Mismo patrón que productos (DEC-33, DEC-85); PR-31 sigue abierta para más datos |
| S-2 | Las pantallas de H3 son solo del Administrador; el menú activa "Proveedores" y "Stock" | Matriz de actores de 04; PR-25 abierta |
| S-3 | El total del ingreso se calcula como en la venta: subtotal por línea redondeado a 2 decimales y total como suma (DEC-49) | RI-12 y un mismo criterio de redondeo |
| S-4 | El precio de compra se precarga desde `producto_proveedor` y, al confirmar, se crea o actualiza con el precio del ingreso; anular el ingreso no lo revierte | 05: "último precio conocido; sugiere el precio en CU-05" |
| S-5 | Producto nuevo desde el ingreso con un diálogo y el servicio de CU-11, como DEC-62 | Mismo patrón que la venta |
| S-6 | Ingresos y pagos no se editan: se anulan con motivo, solo el Administrador, y se cargan de nuevo. Ingreso: solo sin pagos vigentes; devuelve el stock con `mover_stock` (negativo permitido, DEC-46). Pago: por transferencia, siempre; en efectivo, solo con la caja de su egreso abierta, con una reversa `INGRESO` de concepto propio `ANULACION_PAGO` en la misma caja, vinculada al pago, a nombre de quien anula y con el motivo; el egreso original no se toca y hay una sola reversa por pago. Nada se borra | Mismo patrón que la anulación de ventas (DEC-45, DEC-66 a DEC-68, DEC-72) |
| S-7 | La fecha del ingreso es la de hoy y no se edita; la fecha del remito, si hace falta, va en `observacion` | Un solo criterio de fecha y sin ingresos con fecha inventada |
| S-8 | Un ingreso puede incluir carne (sin control de stock): queda en la deuda y el stock no cambia | RI-07 y DEC-36; el proveedor de carne también cobra |
| S-9 | Listados de proveedores, ingresos, pagos y stock paginados de a 25, como productos y el historial de ventas | Mismo patrón (DEC-86) |

## Cambios después de aprobar el spec

| Fecha | Cambio | Decisión | Etapa |
|---|---|---|---|
| 2026-10-29 | Stock editable por el Administrador al crear y modificar productos, con cada cambio registrado en `ajuste_stock`; salía de "Fuera de H3" (PR-32, cerrada como supuesto). Spec propio (`SPEC-H3-etapa1b.md`); se hace en la etapa 1b, antes de proveedores. Reemplaza el primer diseño (CU-15, pantalla aparte) | DEC-98 | 1b |
| 2026-10-29 | Stock inicial en el alta del Administrador, registrado como ajuste | DEC-99 | 1b |
| 2026-10-29 | Panel: alta y modificación de productos con el servicio de catálogo; `ajuste_stock` de solo lectura | DEC-100 | 1b |
| 2026-10-29 | Alerta sin mínimo con `stock_actual <= 0` (criterio 11 y regla de consulta-stock) | DEC-101 | 5 |
| 2026-10-29 | Aviso de stock insuficiente al agregar en la venta, sin cantidades; cambia el comportamiento de la venta (pedido por el alumno) | DEC-102 | 5 |
