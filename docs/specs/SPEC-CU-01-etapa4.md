# SPEC - CU-01 Alta de producto durante la venta y anulación de ventas (H2, etapa 4)

**Estado:** aprobado, con un cambio en la decisión 7 (concepto `ANULACION`).

Fuente de verdad: `/docs`. Este spec no agrega reglas del negocio. Toma las de CU-01 A1 y CU-11 (04), RF-17 (03), RN-03 y RN-05 (04), RI-02, RI-07 y RI-13 (05), DEC-45, DEC-46, DEC-47, DEC-52 y DEC-57 (09), y los casos CP-05, CP-55, CP-56 y CP-85 (08). Lo que `/docs` no fijaba está en la sección final (DEC-62 a DEC-74).

El spec de la etapa 2 (`SPEC-CU-01.md`) dejó estos dos temas fuera de su alcance; este archivo los cubre sin modificarlo.

## 0. Módulos

| Módulo | Qué hace | Depende de |
|---|---|---|
| A. Alta durante la venta | La cajera con permiso crea un producto desde la pantalla de venta, sin perder la venta en curso, y lo agrega a la lista | Venta (CU-01, etapa 2) y alta de productos (CU-11, H1) |
| B. Anulación de ventas | El Administrador anula una venta de la caja abierta con motivo; en la misma operación se revierten el ingreso de caja y el stock | Venta (etapa 2) y caja (etapas 1 y 3) |

A y B no dependen entre sí. Orden de construcción: A y después B, porque A no cambia el modelo y B trae una migración.

## 1. Objetivo

**A.** Si la cajera busca un producto que no está en el catálogo y tiene permiso de alta, lo crea ahí mismo y sigue cobrando. Sin permiso, no ve la opción y el servidor la rechaza.

**B.** Una venta confirmada no se edita ni se borra. Si se cargó mal, el Administrador la anula mientras su caja esté abierta: la venta queda marcada como anulada, la caja registra un egreso que devuelve su monto y el stock vuelve a sumar lo vendido. Con la caja cerrada no se anula.

**Usuarios:** A, la cajera con `puede_crear_productos` (RN-05). B, solo el Administrador (DEC-45).

**Reglas:**

| Regla | Origen |
|---|---|
| **A.** Solo la cajera con permiso de alta crea productos desde la venta. Sin permiso, el servicio, la pantalla y la URL directa lo rechazan (403) | RN-05, RF-17, CP-55, CP-56 |
| **A.** El alta usa el mismo servicio y las mismas validaciones que CU-11 (`crear_producto`): plus interno no repetido, unidad obligatoria, `stock_actual` en 0 | CU-11 A1, RI-07 |
| **A.** La venta en curso no se pierde al crear el producto: sigue en el navegador y el producto nuevo se agrega a la lista | DEC-47 |
| **A.** Un producto nuevo con control de stock arranca en 0: si se vende, se aplica el aviso de stock insuficiente y el stock queda negativo | DEC-46 |
| **B.** Solo el Administrador anula. La cajera y los Dueños, no (403) | DEC-45, RN-06 |
| **B.** Solo se anula una venta cuya caja está `ABIERTA`. Con la caja cerrada se rechaza | DEC-45, RN-03, RI-02, CP-05, CP-85 |
| **B.** En una sola operación: la venta pasa a anulada, se registra un egreso de reversa por su total y con su medio de pago, y los productos con control de stock suman la cantidad vendida | DEC-45, RI-07, RNF-10, CP-85 |
| **B.** La venta, sus detalles y su ingreso de caja no se modifican ni se borran; solo cambia el estado de la venta | DEC-45, 05 (7.1) |
| **B.** Una venta anulada no se vuelve a anular | DEC-45 |

**Fuera de esta etapa:** anulación parcial (de una línea), anulación de ventas de cajas cerradas, consultas de ventas por rango (CU-09, H5), venta a cuenta corriente (H4), modificar o dar de baja productos desde la venta (sigue siendo del Administrador en CU-11).

**Criterios de aceptación:**
1. La cajera con permiso busca "Matambre de cerdo", no hay resultados, toca "Crear producto", completa los datos y el producto queda creado y agregado a la venta, con los productos que ya tenía cargados. Confirma la venta y se registra (CP-56 durante la venta).
2. Con un plus interno repetido, el alta se rechaza junto al campo y la venta en curso sigue igual (CU-11 A1).
3. La cajera sin permiso no ve "Crear producto", y un POST directo al alta desde la venta devuelve 403 (CP-55).
4. Con la caja abierta, fondo $ 5.000 y una venta en efectivo de $ 19.250 con 2 unidades de un producto con stock, el Administrador la anula con motivo: la venta queda anulada, hay un egreso `ANULACION` de $ 19.250 en efectivo que la referencia, el stock vuelve a subir 2 y el esperado de efectivo del cierre vuelve a $ 5.000 (CP-85).
5. Sin motivo, la anulación se rechaza. Anular otra vez la misma venta se rechaza. Con la caja cerrada se rechaza (CP-85, CP-05).
6. La cajera y los Dueños reciben 403 en las pantallas de anulación; sin sesión, ingreso.
7. El ticket de una venta anulada lo muestra como anulada, y el resumen del día del inicio no la cuenta.

## 2. Comandos

```bash
source .venv/bin/activate
npm run estilos
python manage.py check
python manage.py makemigrations --check --dry-run
ruff check . && ruff format --check .
pytest
```

## 3. Estructura

| Archivo | Cambio |
|---|---|
| `apps/ventas/views.py` y `urls.py` | **A:** `/ventas/producto/` (POST, JSON) que llama a `crear_producto` y devuelve el producto como lo devuelve la búsqueda. **B:** `/ventas/` (ventas de la caja abierta), `/ventas/<id>/` (detalle con el formulario de anulación) y `/ventas/<id>/anular/` (POST) |
| `apps/ventas/forms.py` | **B:** `AnularVentaForm` (motivo). **A** reusa `ProductoForm` de catálogo |
| `templates/ventas/nueva.html` y `static/js/venta.js` | **A:** botón "Crear producto" cuando la búsqueda no trae resultados y un `<dialog>` con el formulario de alta |
| `apps/ventas/models.py` y una migración `ventas/0003` | **B:** estado de la venta y datos de la anulación (decisión 6) |
| `apps/ventas/services.py` | **B:** `puede_anular(usuario)`, `ventas_de_la_caja_abierta()` y `anular_venta(usuario, venta, motivo)`. `resumen_del_dia` deja de contar las anuladas |
| `apps/caja/models.py` y una migración `caja/0006` | **B:** concepto `ANULACION` en `movimiento_caja`, en la restricción de RI-13 (referencia a la venta), solo como egreso y una sola reversa por venta |
| `apps/caja/services.py` | **B:** `registrar_reversa_venta(venta, usuario, motivo)`, junto a `registrar_ingreso_venta` |
| `apps/comun/menu.py` | **B:** función nueva para el Administrador que lleva a `/ventas/` (decisión 10) |
| `templates/ventas/` | **B:** plantillas nuevas `lista.html` y `detalle.html`; `ticket.html` muestra la marca de anulada |
| `apps/ventas/tests/` | Pruebas nuevas (sección 5) |

Al terminar se actualizan los docs: 04 (nota de implementación de CU-01 A1 y de la anulación; matriz de actores con la anulación del Administrador), 05 (`venta.estado` y campos de anulación, concepto `ANULACION` en `movimiento_caja`), 08 (CP-56 durante la venta y CP-85 automatizados), 09 (decisiones de este spec) y 07 (estado de H2).

## 4. Estilo de código

- Igual que las etapas anteriores: las reglas viven en el servicio, la vista muestra sus `ValidationError` y todo lo que escribe va en una transacción.
- La anulación bloquea la fila de la caja con `select_for_update`, igual que la venta y el cierre, para que una anulación y un cierre no se crucen.
- El stock se devuelve con `F("stock_actual") + cantidad`, igual que la venta lo descuenta.
- Dinero con `Decimal`, nunca `float`.
- La interfaz usa los mismos componentes de Tailwind (DEC-30). El alta en la venta reusa los campos y textos de `ProductoForm`.

Ejemplo de la forma del servicio (orientativo):

```python
def anular_venta(usuario, venta, motivo):
    """DEC-45: anula la venta de una caja abierta y revierte caja y stock en una operación."""
    if not puede_anular(usuario):
        raise PermissionDenied("Solo el administrador anula ventas.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Escribí por qué se anula la venta."})
    with transaction.atomic():
        caja = Caja.objects.select_for_update().get(pk=venta.caja_id)
        venta = Venta.objects.select_for_update().get(pk=venta.pk)
        ...
```

## 5. Pruebas

| Prueba | Nivel | Caso |
|---|---|---|
| Cajera con permiso crea un producto desde la venta: se crea con stock 0 y vuelve con los datos de la búsqueda | Servicio y pantalla | CP-56, RF-17 |
| Cajera sin permiso, Administrador y Dueños: el alta desde la venta da 403 | Pantalla | CP-55, RN-05 |
| Plus repetido o datos inválidos: errores por campo, no se crea nada | Pantalla | CU-11 A1, RI-16 |
| Venta con el producto recién creado con control de stock: aviso y stock negativo | Servicio | DEC-46 |
| Anulación con motivo: venta anulada con fecha y usuario, egreso de reversa con su medio, monto y referencia, stock devuelto solo en productos con control de stock | Servicio | CP-85, RI-07, RI-13 |
| Después de anular, el esperado del cierre por medio vuelve al valor sin la venta | Servicio | CP-07, DEC-45 |
| Anulación sin motivo, de una venta ya anulada o con la caja cerrada: se rechaza y no cambia nada | Servicio | CP-85, CP-05, RI-02 |
| Reversa en efectivo que dejaría el efectivo esperado por debajo de 0: se rechaza | Servicio | DEC-69 |
| Una anulación y un cierre a la vez no se cruzan (bloqueo de la fila) | Servicio | RNF-10 |
| Restricciones de la base: estado válido y datos de anulación solo si está anulada | Integridad | 05 (7.4) |
| Resumen del día sin anuladas; ticket con la marca de anulada | Servicio y pantalla | DEC-45 |
| Pantallas de lista, detalle y anulación; permisos: cajera y Dueños 403, sin sesión ingreso | Pantalla | RF-02, RNF-06 |

Recorridos manuales con Playwright en localhost, con datos de ejemplo: alta durante la venta y anulación de una venta en efectivo con revisión del cierre. Además queda pendiente registrar RM-04 (tarea aparte de la etapa).

## 6. Límites

**Siempre:**
- Correr check, ruff y pytest antes de proponer el cambio.
- Poner cada regla en el servicio, con su prueba.
- Actualizar `/docs` en el mismo cambio.

**Preguntar antes:**
- Cualquier regla que no esté en este spec.
- Aplicar migraciones sobre la base de desarrollo (aprobado para `caja/0006` y `ventas/0003`).
- Hacer commit.

**Nunca:**
- Borrar o modificar una venta, sus detalles o sus movimientos de caja más allá del estado y los datos de anulación.
- Tocar una caja cerrada o sus movimientos.
- Usar `float`, leer `.env` o usar datos reales.

## Decisiones del spec

Aprobadas y registradas en 09 como DEC-62 a DEC-74, en el mismo orden. No son datos del negocio: son decisiones de diseño (DEC-35).

**Alta durante la venta (A)**

1. **Dónde se hace el alta.** En un diálogo sobre la pantalla de venta, con los mismos campos que `/productos/nuevo/`. Así la lista de la venta, que vive en el navegador (DEC-47), no se pierde. La alternativa, ir a `/productos/` y volver, obliga a guardar la venta en curso en algún lado.
2. **Cuándo aparece "Crear producto".** Solo para la cajera con permiso y cuando la búsqueda no trae ningún resultado (es la condición de A1: "producto no encontrado").
3. **Qué se precarga.** Si el texto buscado tiene solo dígitos, va al plus interno (lo trajo el lector, DEC-37); si no, va al nombre.
4. **Después de crear.** El producto se agrega a la venta igual que con un código exacto (DEC-52): por unidad con cantidad 1; por kg, con el cursor en la cantidad.

**Anulación (B)**

5. **Motivo obligatorio.** El Administrador escribe por qué anula; sin motivo no se anula. DEC-45 no lo pide explícitamente, pero sin motivo la anulación no se puede explicar después.
6. **Cambio de modelo.** En `venta`: `estado` (`CONFIRMADA` por defecto, `ANULADA`), `anulada_en`, `anulada_por_usuario` y `motivo_anulacion`. Restricciones en la base: estado válido, y los tres datos de anulación presentes si y solo si la venta está anulada. Las ventas existentes quedan `CONFIRMADA`.
7. **Cómo es el egreso de reversa.** Un `movimiento_caja` `EGRESO` con un concepto nuevo `ANULACION`, que referencia la venta, con su medio de pago y su total, el usuario que anula y el motivo en `descripcion`. La restricción de RI-13 suma `ANULACION` con referencia a la venta; además, `ANULACION` solo puede ser egreso y hay a lo sumo una por venta. El esperado del cierre (ingresos − egresos por medio) la descuenta sin cambios, y se verifica con una prueba. Agrega un valor a la lista de conceptos (PR-10).
8. **Reversa en efectivo sin efectivo suficiente.** Si la venta fue en efectivo y la reversa deja el efectivo esperado de la caja por debajo de 0 (por ejemplo, después de un retiro), se rechaza, igual que un egreso "otro" (DEC-57): no se puede devolver efectivo que no está. La alternativa es permitirlo y que aparezca como diferencia en el cierre.
9. **Qué stock se devuelve.** El de los productos que hoy tienen control de stock, aunque estén dados de baja. Como la anulación es solo con la caja abierta, es muy raro que `controla_stock` haya cambiado entre la venta y la anulación; no se guarda el valor de ese momento.
10. **Pantallas del Administrador.** Una función nueva en el menú del Administrador, "Ventas del turno" (`/ventas/`), con las ventas de la caja abierta (hora, cajera, medio, total y estado) y el detalle de cada una con el botón "Anular venta", el motivo y una confirmación. Sin caja abierta, la pantalla lo dice. Las ventas de cajas cerradas no se listan (se consultan en CU-09, H5). Esto suma al Administrador en la matriz de actores de 04 para la anulación (DEC-45), no para registrar ventas.
11. **Caja abierta de otro día.** Se puede anular una venta de una caja abierta de otro día: DEC-45 solo pide que la caja esté abierta, y DEC-50 frena la venta, no la anulación.
12. **Cómo se ve una venta anulada.** El ticket y el detalle muestran "Anulada", con fecha, quién y motivo. El resumen del día del inicio no cuenta las anuladas; la lista de últimas ventas las muestra con la marca. El reporte de cierre no cambia: la reversa ya está en el esperado del medio. *Ajustado después por DEC-77: el cierre y su reporte listan las ventas anuladas.*
13. **Orden dentro de la etapa.** Primero A (sin migración) y después B.

## Cambios después de aprobar el spec

Surgieron del recorrido RM-04 y de la revisión de H2, y están registrados en 09 y 08:

- **DF-01 (DEC-75, DEC-76):** `static/js/lector.js` detecta una lectura del lector en el campo de cantidad y la busca como producto; Enter en la cantidad vuelve al buscador. El servidor rechaza más de 100 kg o 100 unidades por línea (supuesto del proyecto, pendiente de PR-36). Pruebas: CP-87 y `apps/ventas/tests/js/lector.test.cjs`.
- **DF-02:** la tabla de la venta se desplaza dentro de su recuadro en el celular.
- **DEC-77:** el cierre y su reporte listan las ventas anuladas.
- **DEC-46:** el registro del faltante de stock queda abierto en PR-37.
