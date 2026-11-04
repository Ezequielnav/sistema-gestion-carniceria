# SPEC - H4 Clientes y cuentas corrientes (CU-12, SC-01, SC-03, CU-04, CU-08)

**Estado:** aprobado (S-1 a S-11 como DEC-120 a DEC-130; R-1 a R-7 como DEC-131).

Fuente de verdad: `/docs`. Este spec no agrega reglas del negocio. Toma las de CU-04, CU-08, CU-12, SC-01 y SC-03 (04), RF-18 y RF-35 a RF-41 (03), RN-04, RN-07 y RN-11 (04), RI-05, RI-06, RI-13, RI-15 y RI-18 (05), DEC-107 a DEC-119 (09) y los casos CP-18, CP-19 y CP-40 a CP-44 (08). Las preguntas de H4 (PR-11 a PR-16 y PR-31) están cerradas como **supuestos del proyecto, no datos confirmados por el negocio** (DEC-107). Lo que `/docs` no fijaba está en la sección final (S-1 a S-11, DEC-120 a DEC-130) y los ajustes del refactor, en R-1 a R-7 (DEC-131), igual que en el spec de H3. Si el spec cambia después de aprobado, se anota en "Cambios después de aprobar el spec".

## 0. Módulos

Cada caso de uso conserva su ID de 04: SC-03 es la venta a cuenta corriente, CU-04 el cobro, CU-08 el estado de cuenta, CU-12 la gestión de clientes y SC-01 la elección del cliente.

| Módulo | Qué hace | Depende de |
|---|---|---|
| `cuenta` | Saldo, disponible y deuda vencida de un cliente, calculados al consultar (DEC-21, DEC-108, DEC-109); texto del límite (DEC-115) | — |
| `clientes` (CU-12, SC-01) | Alta, modificación, baja lógica y reactivación de clientes; buscador de clientes para la venta y el cobro | `cuenta` |
| `venta-cc` (SC-03) | Venta a cuenta corriente con límite y alerta; su anulación con `ANULACION_VENTA` (L1) | `clientes`, `cuenta` |
| `cobro` (CU-04) | Cobro con ingreso a caja o sin él; anulación con sus reversas | `clientes`, `cuenta`, caja (funciones públicas, R-1) |
| `estado-cuenta` (CU-08) | Movimientos, saldo, alerta, carga y anulación del saldo inicial y acceso a modificar límite y observaciones | `cuenta` |

Dirección de dependencias (R-4): `ventas` usa `clientes` y `caja`; `clientes` usa `caja`; `clientes` y `caja` nunca importan `ventas`, y `caja` nunca importa `clientes`.

Orden de construcción: `cuenta` y modelo → `clientes` y SC-01 → `venta-cc` y su anulación → `cobro` y su anulación → `estado-cuenta` → cierre.

## 1. Objetivo

El Administrador registra a los clientes con su límite de crédito. La cajera vende a cuenta corriente a un cliente existente, sin pasar su límite, y cobra lo que debe; el Administrador también cobra, aunque no haya caja abierta. El Administrador carga la deuda que cada cliente ya tenía como saldo inicial, consulta el estado de cuenta con la alerta de deuda vencida y anula con movimiento inverso un saldo inicial, una venta a cuenta corriente o un cobro cargado por error.

**Usuarios:** Administrador en todo; cajera en SC-03, CU-04 y SC-01 (sin alta de clientes, DEC-116). Los dueños no acceden (PR-25 sigue abierta).

### Ajustes del refactor de capas

No están escritos en `/docs`: salen de revisar el código que H4 va a tocar.

| ID | Ajuste | Etapa |
|---|---|---|
| R-1 | `caja.services` expone funciones públicas para el ingreso de un cobro (`PAGO_CLIENTE`) y su reversa (`ANULACION_COBRO`), con el mismo bloqueo de caja y control de efectivo que el pago a proveedor (R-3 de H3) | 4 |
| R-2 | La venta y su anulación llaman a `registrar_ingreso_venta` y `registrar_reversa_venta` solo si el medio ingresa a caja; con cuenta corriente llaman a `clientes.services` (cargo y su anulación). Hoy siempre registran el movimiento de caja | 3 |
| R-3 | `clientes.services` concentra saldo, disponible, deuda vencida, límite (parte de RI-05), RI-06 y RI-15. Hoy el servicio está vacío y RI-15 se anota "en el servicio" en el modelo | 1 a 4 |
| R-4 | La prueba de estructura (`test_estructura.py`) suma: `clientes` y `caja` no importan `ventas`; `caja` no importa `clientes` | 1 a 5 |
| R-5 | Los comentarios "a confirmar (PR-12, PR-13, PR-15)" de `apps/clientes/models.py` citan DEC-108, DEC-109 y DEC-111; el panel deja de mostrar `fecha_vencimiento`; los datos de ejemplo cargan dirección y observaciones (antes `condiciones`) | 1 |
| R-6 | `medios_de_pago_para_venta` suma el medio de cuenta corriente (activo con `ingresa_a_caja = false`, DEC-41); el resto de la venta no cambia | 3 |
| R-7 | Los saldos y la marca de deuda vencida del listado de clientes salen de una consulta agrupada para toda la página, no de una consulta por fila (evita repetir L10) | 2 |

### Reglas por módulo

| Regla | Origen |
|---|---|
| **cuenta.** Saldo = `SALDO_INICIAL` + `VENTA_FIADA` + `ANULACION_PAGO` − `PAGO` − `ANULACION_VENTA` − `ANULACION_SALDO_INICIAL`; nunca menor a 0 | DEC-21, DEC-111, DEC-113, DEC-119, CP-42 |
| **cuenta.** Disponible = límite − saldo, si hay límite. Texto: vacío "Sin límite", 0 "Sin crédito habilitado", otro valor el monto | DEC-108, DEC-115 |
| **cuenta.** Deuda vencida: los cobros vigentes se imputan a los cargos vigentes (ventas a cuenta corriente no anuladas y el saldo inicial vigente, con su fecha de origen), del más antiguo al más nuevo; lo que queda sin cubrir de las que tienen más de `PLAZO_VENCIMIENTO_CUENTA_CORRIENTE_DIAS` (30) es la deuda vencida. Solo alerta | DEC-109, DEC-119, RN-11, CP-44 |
| **clientes.** Solo el Administrador da de alta, modifica, da de baja y reactiva. Nombre obligatorio; teléfono, dirección y observaciones (que incluye las condiciones de crédito) opcionales; límite mayor o igual a 0 u omitido. El nombre repetido no se bloquea | RF-35, RF-41, DEC-112, DEC-116, DEC-117, S-1 |
| **clientes.** Buscador por nombre o teléfono entre los activos (en el cobro, también los dados de baja con saldo); listado paginado de a 25 | DEC-116, DEC-118, SC-01 |
| **venta-cc.** Con medio cuenta corriente: cliente activo obligatorio; si tiene límite y saldo + total lo supera, se rechaza mostrando saldo y disponible. Genera `VENTA_FIADA` por el total y ningún movimiento de caja, en la misma operación que la venta | RF-18, RI-05, DEC-108, CP-18, CP-19 |
| **venta-cc.** La alerta de deuda vencida se muestra al elegir el cliente y no frena la venta | DEC-109 |
| **venta-cc.** Anulación con las reglas de DEC-45 (solo el Administrador, motivo, su caja abierta): `ANULACION_VENTA` por el total en lugar del egreso de caja y el stock vuelve (DEC-70). Se rechaza si el saldo actual del cliente es menor al total | DEC-113, DEC-114, L1 |
| **cobro.** Cobran el Administrador y la cajera. Monto mayor a 0 y no mayor al saldo; si lo supera, se rechaza mostrando el saldo como máximo. Cualquier medio activo salvo cuenta corriente | RF-36, RF-37, RI-06, DEC-110, DEC-111, CP-40, CP-41 |
| **cobro.** Con caja abierta del día: `INGRESO` `PAGO_CLIENTE` con su medio en esa caja, en la misma operación. La cajera sin caja abierta del día no cobra. El Administrador puede desmarcar "Entra a la caja abierta" o cobrar sin caja: sin movimiento de caja (`entra_a_caja = false`) | RN-04, DEC-50, DEC-106, DEC-110 |
| **cobro.** Anulación con motivo, solo el Administrador: `ANULACION_PAGO` en la cuenta; si entró a caja, `EGRESO` `ANULACION_COBRO` en la caja de su ingreso, que debe seguir abierta (aunque sea de otro día), y en efectivo sin dejar el esperado por debajo de 0. Con la caja de su ingreso ya cerrada, la anulación se rechaza, con el criterio de H3 para el pago a proveedor que salió de caja (DEC-92, DEC-106). Sin caja, se anula siempre. Una sola reversa por cobro | RN-03, DEC-69, DEC-72, DEC-92, DEC-106, DEC-113 |
| **estado-cuenta.** Saldo, límite (DEC-115), disponible, alerta de deuda vencida y movimientos (saldo inicial, ventas a cuenta corriente, cobros y sus anulaciones) del más nuevo al más viejo, paginados de a 25 | RF-39, RF-40, CU-08 |
| **estado-cuenta.** Saldo inicial: solo el Administrador; monto mayor a 0, fecha de origen no posterior a hoy y motivo obligatorio; uno vigente por cliente; sin caja y sin validar el límite. Anulación con motivo y `ANULACION_SALDO_INICIAL`, rechazada si el saldo actual es menor al monto; después se puede cargar otro | RI-18, DEC-119, CU-08 A4 |

**Fuera de H4:** recargos e intereses (DEC-112, posible mejora futura), saldo a favor (DEC-111), carga de datos históricos de ventas y planillas (PR-28, RF-47; los saldos de clientes no, que entran por DEC-119), comprobante imprimible del cobro, tarjeta de deuda vencida en el inicio, consultas de los dueños (PR-25), reportes de saldos (CU-09, H5), plazo de vencimiento por cliente o editable en pantalla (DEC-109).

### Criterios de aceptación

1. Las migraciones quitan `ANTICIPO` y `fecha_vencimiento`, renombran `condiciones` a `observaciones` sin perder datos y agregan los tipos, el concepto, los campos y las restricciones de 05; las pruebas de ventas, caja y proveedores pasan sin cambios.
2. Un cliente con ventas a cuenta corriente de $ 1.000 (hace 40 días) y $ 500 (hace 5 días) y un cobro de $ 600 tiene saldo $ 900 y deuda vencida $ 400 (CP-42, CP-44, CP-119).
3. El Administrador da de alta, modifica, da de baja y reactiva un cliente; la cajera y los dueños reciben 403 en esas pantallas (CP-114).
4. Con límite $ 1.000 y saldo $ 800, una venta de $ 200 se acepta y una de $ 201 se rechaza mostrando el disponible; con límite vacío se acepta cualquier monto; con límite 0 se rechaza y se ve "Sin crédito habilitado" (CP-115).
5. La venta a cuenta corriente genera `VENTA_FIADA` y ningún movimiento de caja; sin cliente se rechaza (CP-18, CP-19).
6. Anular una venta a cuenta corriente de $ 500 con saldo $ 900 deja saldo $ 400, vuelve el stock y no crea egreso de caja; con saldo $ 300 se rechaza (CP-116).
7. La cajera cobra $ 300 en efectivo con la caja abierta: el saldo baja y la caja tiene un ingreso `PAGO_CLIENTE`; sin caja abierta, se rechaza; un cobro mayor al saldo se rechaza mostrando el máximo; cuenta corriente no aparece entre los medios (CP-40, CP-41, CP-117).
8. El Administrador cobra sin caja abierta: se registra sin movimiento de caja (CP-117).
9. Anular un cobro que entró a caja deja `ANULACION_PAGO` y `ANULACION_COBRO`; con su caja cerrada, se rechaza (mismo criterio que DEC-92 y DEC-106); uno sin caja se anula siempre (CP-118).
10. Un cobro en efectivo, o su anulación, y el cierre de la misma caja al mismo tiempo terminan en un estado coherente, como CP-88 (CP-120).
11. El estado de cuenta muestra saldo, límite, alerta y movimientos con sus anulaciones; solo lo ve el Administrador (CP-121).
12. El Administrador carga un saldo inicial de $ 2.000 con fecha de origen de hace 45 días y motivo: el saldo sube $ 2.000 y aparecen $ 2.000 de deuda vencida; un segundo saldo inicial se rechaza; anularlo con saldo $ 2.000 lo deja en 0 y permite cargar otro; con saldo $ 1.500 la anulación se rechaza; la cajera recibe 403 (CP-122).

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
config/settings.py               PLAZO_VENCIMIENTO_CUENTA_CORRIENTE_DIAS = 30 (DEC-109)
apps/clientes/models.py          tipos, campos y restricciones nuevos (etapa 1)
apps/clientes/services.py        clientes, saldo, disponible, vencida, saldo inicial, cargo y su anulación, cobros (R-3)
apps/clientes/forms.py           cliente, saldo inicial, cobro y sus anulaciones
apps/clientes/views.py, urls.py  CU-12, SC-01 (buscador), CU-04 y CU-08
apps/caja/services.py            ingreso de cobro y su reversa; cobros en el cierre (R-1, S-8)
apps/ventas/services.py          medio cuenta corriente, cargo y anulación sin caja (R-2, R-6)
apps/comun/menu.py               "Clientes" (Administrador) y "Cobrar cuenta corriente" (cajera) (S-2)
templates/clientes/              pantallas de CU-12, CU-04 y CU-08
templates/ventas/, static/js/    elección del cliente en la venta (S-4)
apps/*/tests/                    pruebas por módulo; prueba de estructura (R-4)
docs/                            01, 03, 04, 05, 06, 07, 08 y 09 al día
```

**Migraciones previstas (se piden al llegar a la etapa 1):** en `movimiento_cuenta_corriente`, quitar `ANTICIPO` y `fecha_vencimiento`, agregar `ANULACION_VENTA`, `ANULACION_PAGO`, `SALDO_INICIAL` y `ANULACION_SALDO_INICIAL` con `fecha_origen`, `motivo` y `saldo_inicial_id`, y cambiar las restricciones de referencias y de unicidad (05, sección 7.4); en `pago_cliente`, `entra_a_caja`, `estado` y los datos de anulación con su `CHECK`; en `cliente`, agregar `direccion` y renombrar `condiciones` a `observaciones`; en `movimiento_caja`, el concepto `ANULACION_COBRO` (RI-13: lleva el cobro; siempre es un egreso) con una sola reversa por cobro. Si la base de desarrollo tuviera movimientos `ANTICIPO` o fechas de vencimiento cargadas, la migración se detiene y se avisa antes de tocar nada.

## 4. Estilo de código

El mismo de H2 y H3: vistas finas con `requiere_funcion` y el control del servicio (permisos dobles), reglas en servicios, errores con `ValidationError` por campo, operaciones en `transaction.atomic()` con `select_for_update` donde hay concurrencia (S-9) y docstrings que citan RF, RI y DEC.

```python
def saldo(cliente):
    """Lo que el cliente debe, derivado de sus movimientos (DEC-21).

    Cargos y anulaciones de cobros suman; cobros y anulaciones de ventas restan. Nunca es
    menor a 0 (DEC-111): el cobro y la anulación de ventas lo validan antes de guardar.
    """
```

## 5. Pruebas

- `pytest` con la base de prueba; nada toca la base de desarrollo.
- Cada regla RN y RI de H4 y cada decisión del spec con al menos una prueba, por servicio y por pantalla (permisos con 403).
- Deuda vencida con fechas fijas (sin depender del día en que corre la prueba).
- Prueba de estructura ampliada (R-4).
- Concurrencia: un cobro en efectivo, o su anulación, y el cierre de caja al mismo tiempo, como CP-88; dos ventas a cuenta corriente del mismo cliente al mismo tiempo no pasan juntas el límite.
- CP nuevos propuestos: **CP-114** (gestión de clientes), **CP-115** (límite de crédito), **CP-116** (anulación de venta a cuenta corriente), **CP-117** (cobro con caja y sin caja), **CP-118** (anulación de cobro), **CP-119** (deuda vencida con imputación a lo más antiguo), **CP-120** (cobro y cierre al mismo tiempo) **CP-121** (estado de cuenta) y **CP-122** (saldo inicial y su anulación, RI-18). Los demás ya existen en 08 (CP-18, CP-19, CP-40 a CP-44).
- Recorrido manual con Playwright en localhost con datos de ejemplo al cerrar cada etapa con pantalla, y un RM de H4 en el cierre.

## 6. Límites

- **Siempre:** trabajar en la rama `h4`; correr pruebas, lint, `check` y verificación de migraciones antes de commitear; actualizar `/docs` en el mismo cambio; dinero con `DecimalField`; marcar las DEC de H4 como supuestos del proyecto.
- **Preguntar antes:** cada migración; dependencias nuevas; cambiar el comportamiento de la venta con otros medios, de la anulación de ventas o del cierre de caja más allá de lo que dice este spec; ampliar el alcance a algo de "Fuera de H4".
- **Nunca:** leer `.env` ni datos reales; push o PR sin pedido; inventar reglas del negocio (lo que falte va como pregunta y DEC); presentar un supuesto como dato confirmado; borrar ventas, cobros o movimientos.

## 7. Etapas

| Etapa | Alcance | CU / RF / DEC | CP |
|---|---|---|---|
| 1. Modelo y cuenta | Migraciones de la sección 3 (incluye `SALDO_INICIAL`, su anulación y `observaciones`); constante del plazo; servicio `cuenta` (saldo, disponible, deuda vencida con el saldo inicial por su fecha de origen, texto del límite); R-3 (base), R-4, R-5; panel y datos de ejemplo al día | RI-05, RI-06, RI-13, RI-15, RI-18 (restricciones); DEC-108, DEC-109, DEC-111, DEC-113, DEC-115, DEC-117, DEC-119 | CP-42, CP-43, CP-119 |
| 2. Clientes y SC-01 | CU-12 con el patrón de CU-13; menú "Clientes"; listado con saldo y marca de deuda vencida (R-7); buscador de clientes para la venta y el cobro | CU-12, SC-01; RF-35, RF-41; DEC-112, DEC-115 a DEC-118; S-1, S-2, S-7 | CP-114 |
| 3. Venta a cuenta corriente | SC-03 en `/ventas/nueva/`: medio cuenta corriente, elección del cliente con saldo, límite y alerta, `VENTA_FIADA` sin caja, ticket con el cliente; anulación con `ANULACION_VENTA` (L1); R-2, R-6 | SC-03, CU-01 A2; RF-18; RI-05; DEC-108, DEC-109, DEC-113, DEC-114; S-3 a S-5, S-9 | CP-18, CP-19, CP-115, CP-116 |
| 4. Cobro | CU-04 para el Administrador y la cajera: caja abierta del día o sin caja (Administrador), tope en el saldo, anulación con sus reversas; cobros en el cierre de caja; R-1 | CU-04; RF-36, RF-37; RN-04; RI-06, RI-13; DEC-110, DEC-111, DEC-113; S-6, S-8, S-9 | CP-40, CP-41, CP-117, CP-118, CP-120 |
| 5. Estado de cuenta | CU-08: saldo, límite, disponible, alerta y movimientos con sus anulaciones; carga y anulación del saldo inicial (A4); enlaces a modificar el cliente (límite y observaciones), cobrar y anular un cobro | CU-08; RF-39 a RF-41; RN-11; RI-18; DEC-109, DEC-112, DEC-115, DEC-119; S-9, S-10 | CP-44, CP-121, CP-122 |
| 6. Cierre de H4 | Prueba integral (venta a cuenta corriente, cobro, anulaciones y cierre de caja), recorrido manual en localhost, revisión, 07 y 08 al día y Pull Request | Todos los de H4 | Todos los de H4; RM nuevo |

## Decisiones del spec (DEC-120 a DEC-130)

| ID | Decisión | Por qué |
|---|---|---|
| S-1 | CU-12 igual que CU-13: listado de activos con "Incluir dados de baja", alta, modificación, baja con confirmación y "Reactivar". Dar de baja a un cliente con saldo se permite, con un aviso del saldo en la confirmación | Mismo patrón (DEC-85, DEC-87); la baja no borra la deuda y el cobro sigue posible (DEC-116) |
| S-2 | Menú: "Clientes" (listado, estado de cuenta y cobro) para el Administrador; "Cobrar cuenta corriente" para la cajera, que abre solo el cobro (CU-04). La función "Clientes" deja de figurar como "Pronto" | DEC-110 y DEC-116: la cajera cobra pero no gestiona clientes |
| S-3 | La venta trata como cuenta corriente al medio activo con `ingresa_a_caja = false` (DEC-41), sin un campo nuevo; si no hay ninguno activo, la venta no ofrece cuenta corriente | Es el único medio que no entra a caja; el mismo criterio que usa DEC-106 para excluirlo |
| S-4 | En la venta, al elegir cuenta corriente aparece la elección del cliente (SC-01) con saldo, límite (DEC-115), disponible y alerta de deuda vencida. El servidor vuelve a validar cliente, límite y saldo al confirmar (DEC-47). La venta en curso guardada en la pestaña recuerda el cliente | La cajera ve el problema antes de cobrar; el servidor sigue sin aceptar valores del navegador |
| S-5 | El ticket de una venta a cuenta corriente muestra el nombre del cliente y el medio "Cuenta corriente", sin el saldo. El cierre de caja no la cuenta (no hay movimiento); el resumen del día y el historial sí, como venta | El saldo es dato del cliente y el ticket puede quedar a la vista; la caja solo cuenta lo que entra (DEC-56) |
| S-6 | El cobro muestra el saldo como monto máximo y no tiene valor por defecto en el medio (como DEC-51). La opción "Entra a la caja abierta" solo la ve el Administrador, marcada cuando hay caja abierta del día | DEC-110 y DEC-111 en la pantalla |
| S-7 | El listado de clientes muestra saldo, límite (DEC-115) y la marca de deuda vencida, con el filtro "Solo con deuda vencida" | Es el lugar donde DEC-109 pide la alerta, y el filtro evita recorrer páginas |
| S-8 | La pantalla de cierre y su reporte listan los cobros del turno y sus reversas (hora, cliente, monto y medio), como las ventas anuladas (DEC-77) y los pagos a proveedores; caja los lee de `movimiento_caja` sin importar `clientes` | Cambian lo esperado del cierre y sin la lista no se explican |
| S-9 | Bloqueos en un orden fijo: caja, después cliente, después productos por id. La venta a cuenta corriente, el cobro, el saldo inicial y las anulaciones bloquean al cliente para validar límite, saldo y RI-18 | Evita que dos operaciones pasen juntas el límite o el saldo, y las trabas de DF-03 |
| S-10 | El estado de cuenta es solo del Administrador; la cajera ve el saldo en la venta y en el cobro | Matriz de 04: CU-08 es del Administrador; los dueños siguen en PR-25 |
| S-11 | Saldos iniciales, cobros y ventas a cuenta corriente no se editan: se anulan y se cargan de nuevo. La anulación de un saldo inicial o de un cobro se hace desde el estado de cuenta; la de una venta, desde el historial de ventas | Mismo patrón que DEC-45 y DEC-92 |

## Cambios después de aprobar el spec

| Fecha | Cambio | Decisión | Etapa |
|---|---|---|---|
| 2026-11-03 | La anulación de una venta bloquea caja, venta y cliente, en ese orden (S-9) | DEC-128 ampliada | 3 |
| 2026-11-04 | La anulación de un cobro bloquea la caja de su ingreso, el cobro y el cliente, en ese orden (S-9) | DEC-128 ampliada | 4 |
