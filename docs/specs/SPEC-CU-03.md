# SPEC - CU-03 Cerrar caja y egresos "otros" (H2, etapa 3)

**Estado:** aprobado.

Fuente de verdad: `/docs`. Este spec no agrega reglas del negocio. Toma las de CU-03 y SC-02 (04), RF-06 a RF-09 (03), RN-03 (04), RI-02, RI-10 y RI-13 (05), DEC-38, DEC-40 y DEC-43 (09), y los casos CP-04 a CP-07 y CP-81 (08). Las decisiones que `/docs` no fijaba están en la sección final (DEC-55 a DEC-61).

## 0. Módulos

| Módulo | Qué hace | Depende de |
|---|---|---|
| A. Egresos "otros" | La cajera registra gastos y retiros en efectivo de la caja abierta | Caja abierta (CU-02) |
| B. Cierre de caja | Resumen por medio de pago, montos contados, diferencias, motivo, bloqueo y reporte | Ventas (CU-01) y egresos (A) |

Orden de construcción: A y después B, porque el efectivo esperado del cierre resta los egresos.

## 1. Objetivo

Al terminar el turno, la cajera cierra la caja: ve cuánto debería haber por cada medio de pago, carga lo que contó y el sistema calcula las diferencias. Si alguna no es cero, tiene que escribir un motivo. Al cerrar, la caja queda bloqueada y se genera el reporte de cierre. Durante el turno, puede registrar egresos "otros" (gastos y retiros en efectivo) para que el efectivo del cierre cuadre.

**Usuario:** el rol Cajera (matriz de actores de 04), con o sin permiso de alta. Cualquier cajera puede cerrar la caja abierta, la haya abierto ella o no.

**Reglas:**

| Regla | Origen |
|---|---|
| **A.** Un egreso "otro" se registra en la caja abierta, en efectivo, con monto mayor a 0 y descripción obligatoria, concepto `OTRO` y sin referencia a venta ni pagos | SC-02, DEC-43, RI-13, CP-81 |
| **A.** Una caja cerrada no recibe egresos | RN-03, RI-02, CP-05 |
| **B.** Lo esperado por medio de pago (`monto_sistema`) es ingresos − egresos de ese medio en la caja. Para el efectivo se suma además el fondo de cambio | RF-07, DEC-38, CP-07 |
| **B.** La cajera carga lo contado de cada medio, mayor o igual a 0. Un valor inválido se rechaza junto al campo | RF-07, CU-03 A1 |
| **B.** Diferencia = contado − esperado, por medio de pago. Se muestra y no se guarda | RI-10, CP-04 |
| **B.** Si alguna diferencia no es cero, se avisa y se exige un motivo (`observacion_cierre`). No hace falta autorización | RF-09, DEC-40, CU-03 A2, CP-06 |
| **B.** Al cerrar, en una sola operación: se guarda un `cierre_caja_detalle` por medio (esperado y contado), la caja pasa a `CERRADA` con `cerrada_en` y `cerrada_por_usuario`, y desde ahí no recibe ventas ni movimientos | RF-08, RN-03, RI-02, RNF-10, CP-05 |
| **B.** Después del cierre se ve el reporte de cierre: caja, turno, fecha, quién abrió y cerró, por medio esperado, contado y diferencia, y el motivo | RF-08, DEC-40 |
| **B.** Se puede cerrar una caja abierta de otro día (es la forma de destrabar la venta de hoy, DEC-50) | DEC-39, DEC-50 |

**Fuera de esta etapa:** pagos a proveedores desde la caja (CU-07, H3), pagos de clientes (CU-04, H4), anulación de ventas (etapa 4), reportes de cierres por rango (CU-09, H5).

**Criterios de aceptación:**
1. Con la caja abierta, la cajera registra un retiro de $ 2.000 con descripción; sin descripción o con monto 0 se rechaza (CP-81).
2. Con fondo $ 5.000, una venta en efectivo de $ 19.250, una con Tarjeta de $ 4.500 y el retiro de $ 2.000, el cierre muestra esperado Efectivo $ 22.250 y Tarjeta $ 4.500 (CP-07).
3. Contando lo mismo que lo esperado, la caja cierra sin motivo. Con una diferencia, no cierra sin motivo y con motivo sí (CP-04, CP-06).
4. Después de cerrar, la caja no acepta ventas ni egresos, la pantalla de Caja ofrece abrir el turno siguiente y se ve el reporte (CP-05).
5. El Administrador y los Dueños no cierran ni registran egresos (403), pero sí ven el reporte de cierre. Sin sesión, ingreso.

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
| `apps/caja/models.py` y una migración `caja/0005` | Solo si se aprueba la decisión 1: `medio_pago.es_efectivo` con un único medio en `true` |
| `apps/caja/services.py` | `registrar_egreso_otro(usuario, monto, descripcion)`, `efectivo()`, `resumen_de_cierre(caja)` (esperado por medio) y `cerrar_caja(usuario, contados, observacion)`. El cierre bloquea la fila de la caja con `select_for_update`, igual que la venta, para que no se cuele una venta durante el cierre |
| `apps/caja/forms.py` | `EgresoForm` (monto, descripción) y `CierreForm` (un campo de contado por medio y el motivo) |
| `apps/caja/views.py` y `urls.py` | `/caja/egreso/` (POST), `/caja/cerrar/` (GET y POST) y `/caja/<id>/cierre/` (reporte) |
| `templates/caja/` | La pantalla de Caja suma el formulario de egreso, la lista de egresos del turno y el botón "Cerrar caja". Plantillas nuevas `cerrar.html` y `cierre.html` |
| `apps/caja/tests/` | Pruebas nuevas (sección 5) |

Al terminar se actualizan los docs: 04 (nota de implementación de CU-03 y SC-02), 05 (si cambia `medio_pago`), 08 (CP-04 a CP-07 y CP-81 automatizados) y 07 (estado de H2).

## 4. Estilo de código

- Igual que CU-02 y CU-01: las reglas viven en el servicio, la vista muestra sus `ValidationError` y todo lo que escribe va en una transacción.
- Dinero con `Decimal`, nunca `float`. La diferencia se calcula, no se guarda (RI-10).
- La interfaz usa los mismos componentes de Tailwind (DEC-30). El prototipo v0 de CU-03 es solo guía (DEC-07); a diferencia de él, hay un campo de contado por medio de pago.

## 5. Pruebas

| Prueba | Nivel | Caso |
|---|---|---|
| Egreso "otro" con monto y descripción: `EGRESO`, concepto `OTRO`, en efectivo, sin referencias | Servicio | CP-81, RI-13 |
| Egreso sin descripción, con monto 0 o negativo, o sin caja abierta: se rechaza | Servicio | CP-81, RI-16 |
| Esperado por medio con ventas, egresos y fondo de cambio | Servicio | CP-07, DEC-38 |
| Cierre sin diferencias: detalles guardados, caja cerrada con fecha y usuario | Servicio | CP-04, RF-08 |
| Diferencia sin motivo se rechaza; con motivo cierra | Servicio | CP-06, DEC-40 |
| Contado negativo o vacío se rechaza junto al campo | Servicio y pantalla | CU-03 A1, RI-16 |
| Caja cerrada: no acepta ventas ni egresos | Servicio | CP-05, RI-02 |
| Cierre de una caja de otro día | Servicio | DEC-50 |
| Una venta y un cierre a la vez no se cruzan (bloqueo de la fila) | Servicio | RNF-10 |
| Pantallas: egreso, cierre con diferencia y reporte | Pantalla | RF-07, RF-08 |
| Permisos: Administrador y Dueños 403; sin sesión, ingreso | Pantalla | RF-02, RNF-06 |

Recorrido manual con Playwright en localhost: RM-03 (abrir caja, tres ventas con distintos medios de pago y cerrar con diferencia).

## 6. Límites

**Siempre:**
- Correr check, ruff y pytest antes de proponer el cambio.
- Poner cada regla en el servicio, con su prueba.
- Actualizar `/docs` en el mismo cambio.

**Preguntar antes:**
- Cualquier regla que no esté en este spec.
- Aplicar una migración sobre la base de desarrollo.
- Hacer commit.

**Nunca:**
- Guardar la diferencia de caja (RI-10).
- Modificar una caja cerrada o sus movimientos.
- Usar `float`, leer `.env` o usar datos reales.

## Decisiones del spec

Aprobadas y registradas en 09 como DEC-55 a DEC-61, en el mismo orden:

1. **Cómo se reconoce el efectivo.** El fondo de cambio y los egresos "otros" son en efectivo, así que el sistema tiene que saber cuál es ese medio. Propongo agregar `medio_pago.es_efectivo` (boolean, un solo medio en `true`) en una migración chica. La alternativa, buscar el medio por el nombre "Efectivo", depende de cómo se escriba en el panel.
2. **Medios que aparecen en el cierre:** todos los activos que ingresan a caja, más cualquier otro que tenga movimientos en esa caja. Cada uno se muestra aunque su esperado sea 0, para que la cajera cuente todo.
3. **Egreso mayor al efectivo disponible:** se rechaza si deja el efectivo esperado por debajo de 0, porque no puede salir de la caja más efectivo del que hay. La alternativa es permitirlo y dejar que aparezca como diferencia.
4. **Lista de egresos del turno:** la pantalla de Caja muestra los egresos registrados (hora, monto, descripción). No se editan ni se borran; un error se corrige en el cierre con el motivo.
5. **Quién ve el reporte de cierre:** la cajera, después de cerrar, y el Administrador y los Dueños desde un enlace directo a `/caja/<id>/cierre/`. Las consultas de cierres por fecha quedan para CU-09 (H5).
6. **Después de cerrar:** se muestra el reporte con un botón "Imprimir" y un enlace a Caja, desde donde se abre el turno siguiente.
7. **Orden dentro de la etapa:** primero los egresos (módulo A) y después el cierre (módulo B).
