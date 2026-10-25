# SPEC - CU-01 Registrar venta (H2, etapa 2)

**Estado:** aprobado.

Fuente de verdad: `/docs`. Este spec no agrega reglas del negocio. Toma las de CU-01 (04), RF-11 a RF-17 (03), RN-04 y RN-05 (04), RI-03, RI-04, RI-07, RI-12, RI-13 y RI-16 (05), DEC-36, DEC-37, DEC-39, DEC-41, DEC-42, DEC-44 y DEC-46 (09), y los casos CP-10 a CP-17, CP-20, CP-21 y CP-82 a CP-84 (08). Las decisiones de interfaz y de cálculo que `/docs` no fijaba están en la sección final (DEC-47 a DEC-54).

## 1. Objetivo

La cajera registra una venta en pocos pasos (RNF-03): busca o escanea productos, indica cantidades, ve los subtotales y el total, elige el medio de pago y confirma. Al confirmar, en una sola operación (RNF-10), el sistema guarda la venta con sus detalles, registra el ingreso en la caja abierta y descuenta el stock de los productos que lo controlan. Después muestra el ticket.

**Usuario:** solo el rol Cajera, con o sin permiso de alta de productos (matriz de actores de 04). El Administrador y los Dueños no venden.

**Reglas:**

| Regla | Origen |
|---|---|
| Se vende solo con una caja abierta, y la venta va a esa caja (la única abierta). Sin caja abierta, la pantalla lo avisa y enlaza a Caja | RF-15, CU-01 A4, DEC-39, CP-17 |
| Se busca por nombre (contiene) o por plus interno (exacto), solo entre productos activos. Un código del lector que coincide exacto con un plus agrega el producto | RF-11, DEC-37, CP-82 |
| Cada línea guarda el precio del producto en ese momento; cambiar el precio después no altera la venta | RI-12, CP-15 |
| Subtotal de la línea = cantidad × precio unitario. Total de la venta = suma de los subtotales | RF-12, RI-03, CP-10 |
| La cantidad es mayor a 0; precios y totales, mayores o iguales a 0 | RI-16, CP-16 |
| Un solo medio de pago por venta, elegido entre los medios activos que ingresan a caja. Cuenta corriente no se ofrece hasta H4 | RF-13, DEC-41, DEC-42, CP-21 |
| Al confirmar, la venta genera un `movimiento_caja` de tipo `INGRESO` y concepto `VENTA` por el total, con el medio de pago, en la misma operación | RN-04, RI-04, RI-13, SC-02, CP-11 |
| El stock baja solo en los productos con `controla_stock = true`. La carne (`controla_stock = false`) se vende por kg y no toca el stock | RI-07, DEC-36, CP-12, CP-13, CP-20 |
| Si la cantidad supera el stock de un producto que lo controla, la venta se permite con un aviso y el stock puede quedar negativo | CU-01 A3, DEC-46, CP-83 |
| Si algo falla a mitad, no queda nada guardado: ni venta, ni detalles, ni movimiento, ni cambio de stock | RNF-10, CP-14 |
| Cancelar la venta antes de confirmar no registra nada | CU-01 A5 |
| El ticket es un comprobante no fiscal en pantalla, imprimible desde el navegador: negocio, número de venta, fecha y hora, cajera, detalle (producto, cantidad, precio unitario, subtotal), total, medio de pago y "No válido como factura" | RF-14, DEC-44, CP-84 |

**Fuera de esta etapa:** alta de producto durante la venta (CU-01 A1, RF-17: etapa 4), venta a cuenta corriente (A2, SC-03: H4), anulación (DEC-45: etapa 4), cierre de caja y egresos (etapa 3).

**Criterios de aceptación:**
1. Con la caja abierta, la cajera agrega dos productos (uno por búsqueda y otro con el código), elige "Efectivo", confirma y ve el ticket. En la base quedan la venta, dos detalles con su precio, un ingreso de caja por el total y el stock descontado solo en el producto que lo controla (CP-10 a CP-13, CP-82, CP-84).
2. Una venta de carne por kg (por ejemplo, 1,250 kg de asado) suma cantidad × precio por kg al total y no cambia el stock (CP-20).
3. Sin caja abierta, la pantalla no deja vender y enlaza a Caja (CP-17).
4. Vender más de lo que hay en stock muestra un aviso, se permite y el stock queda negativo (CP-83).
5. Si falla el registro del movimiento de caja, no queda nada guardado (CP-14).
6. Cantidad 0 o negativa, un producto inactivo o un medio de pago no permitido se rechazan con un mensaje claro (CP-16).
7. El Administrador y los Dueños reciben 403. Sin sesión, se redirige al ingreso. El menú de la cajera enlaza "Ventas".

## 2. Comandos

```bash
source .venv/bin/activate
npm run estilos                       # si cambian las clases de Tailwind
python manage.py check
python manage.py makemigrations --check --dry-run   # no se esperan migraciones
ruff check . && ruff format --check .
pytest
```

## 3. Estructura

Se siguen las capas de 06 (vistas, servicios y acceso a datos) y el mismo patrón que CU-11 y CU-02.

| Archivo | Cambio |
|---|---|
| `apps/caja/services.py` | `registrar_ingreso_venta(venta)` (SC-02): crea el `movimiento_caja` `INGRESO`/`VENTA`. Rechaza una caja cerrada (RI-02) |
| `apps/ventas/services.py` | `puede_vender(usuario)`, `medios_de_pago_para_venta()`, `buscar_para_venta(texto)` y `registrar_venta(usuario, lineas, medio_pago)`. Esta última hace todo dentro de `transaction.atomic()`: valida, toma los precios de la base (nunca del navegador), calcula subtotales y total, guarda la venta y los detalles, llama a SC-02 y descuenta el stock con `F()` para que dos ventas a la vez no se pisen. Devuelve la venta y la lista de avisos de stock |
| `apps/ventas/forms.py` | Validación de la confirmación: medio de pago y líneas (producto y cantidad) |
| `apps/ventas/views.py` | `nueva` (pantalla de venta), `buscar` (JSON para la búsqueda y el lector), `confirmar` (POST) y `ticket`, todas con `@requiere_funcion("Ventas")` |
| `apps/ventas/urls.py` y `config/urls.py` | `ventas/nueva/`, `ventas/buscar/`, `ventas/confirmar/` y `ventas/<id>/ticket/` |
| `apps/comun/menu.py` | `url` de la función "Ventas" |
| `templates/ventas/nueva.html` y `templates/ventas/ticket.html` | Pantalla de venta y ticket (con estilos de impresión) |
| `static/js/venta.js` | Lista de la venta en el navegador: buscar, agregar, cambiar cantidad, quitar, total, avisos y envío al confirmar |
| `apps/ventas/tests/` | Pruebas nuevas (sección 5) |

Al terminar se actualizan los docs: 04 (nota de implementación de CU-01), 08 (CP-10 a CP-17, CP-20, CP-21 y CP-82 a CP-84 automatizados) y 06 si cambia algo del módulo `ventas`.

## 4. Estilo de código

- Igual que `apps/catalogo` y `apps/caja`:
  - Las reglas viven en el servicio. La vista llama al servicio y muestra sus `ValidationError`.
  - Textos y nombres en español, con comentarios cortos que citan la regla.
- Dinero y cantidades con `Decimal` (`campo_monto` y `campo_cantidad`), nunca `float`. El navegador solo muestra un total orientativo; el que vale es el que calcula el servidor.
- La interfaz usa los mismos componentes de Tailwind (DEC-30). El prototipo v0 es solo guía funcional (DEC-07).
- JavaScript propio y chico (D-03), sin librerías nuevas.

## 5. Pruebas

| Prueba | Nivel | Caso |
|---|---|---|
| Venta con varios productos: total = suma de subtotales y precios copiados | Servicio | CP-10, RI-03, RI-12 |
| Ingreso de caja por el total, con el medio de pago y concepto `VENTA` | Servicio | CP-11, RI-04, RI-13 |
| Stock baja en el producto que lo controla y no cambia en el que no | Servicio | CP-12, CP-13 |
| Carne por kg con cantidad decimal: subtotal correcto y stock sin cambios | Servicio | CP-20 |
| Error forzado en SC-02: no queda venta, detalle, movimiento ni cambio de stock | Servicio | CP-14 |
| Cambiar el precio después de vender no cambia la venta | Servicio | CP-15 |
| Cantidad 0 o negativa, producto inactivo, lista vacía y medio no permitido (cuenta corriente o inactivo) se rechazan | Servicio | CP-16, CP-21, DEC-41 |
| Sin caja abierta se rechaza con mensaje claro | Servicio y pantalla | CP-17 |
| Stock insuficiente: se vende, queda negativo y vuelve el aviso | Servicio | CP-83 |
| Búsqueda por nombre y código exacto, solo activos | Servicio y JSON | CP-82 |
| Ticket con todos los datos y la leyenda | Pantalla | CP-84 |
| Permisos: Administrador y Dueños 403; sin sesión, ingreso; menú con "Ventas" | Pantalla | RF-02, RNF-06 |
| Confirmar con datos manipulados desde el navegador (precio o total distintos) no cambia lo que calcula el servidor | Pantalla | RI-12, RI-03 |

Recorrido manual con Playwright en localhost y datos de ejemplo: RM-04 (venta en pocos pasos, con lector y con búsqueda).

## 6. Límites

**Siempre:**
- Correr check, ruff y pytest antes de proponer el cambio.
- Poner cada regla en el servicio, con su prueba.
- Recalcular en el servidor todo lo que viene del navegador.
- Actualizar `/docs` en el mismo cambio.

**Preguntar antes:**
- Cualquier regla que no esté en este spec.
- Cambiar el modelo de datos (no se espera ninguna migración).
- Hacer commit.

**Nunca:**
- Aceptar precios, subtotales o totales calculados en el navegador.
- Usar `float` para montos o cantidades.
- Cargar ventas desde el panel, que es de solo lectura (DEC-31).
- Leer `.env` o usar datos reales.

## Decisiones del spec

Aprobadas y registradas en 09 como DEC-47 a DEC-54, en el mismo orden:

1. **Dónde vive la lista de la venta:** en el navegador (`venta.js`), que la manda completa al confirmar. Así se evitan una recarga por producto y una tabla de "ventas en curso". La alternativa es una lista en la sesión del servidor, con una recarga por cada cambio.
2. **Cantidades:** los productos por `UNIDAD` admiten solo enteros; los productos por `KG`, hasta 3 decimales.
3. **Redondeo:** el subtotal de cada línea se redondea a 2 decimales, con la mitad hacia arriba. El total es la suma de los subtotales ya redondeados.
4. **Caja de otro día:** si la única caja abierta es de una fecha anterior, no se vende y se pide cerrarla, para que las ventas de hoy no queden en el cierre de otro día.
5. **Medio de pago:** sin valor por defecto. La primera opción es "Elegí un medio de pago", igual que el turno y la unidad.
6. **Lector y búsqueda:** un código exacto agrega el producto. Si es por `UNIDAD`, entra con cantidad 1. Si es por `KG`, el cursor queda en la cantidad para cargar el peso. Si el texto no coincide exacto, se muestra la lista de resultados para elegir.
7. **Producto repetido:** si se vuelve a agregar un producto que ya está en la lista, se suma a esa línea en lugar de crear otra.
8. **Después de confirmar:** se muestra el ticket con los botones "Imprimir" y "Nueva venta".
