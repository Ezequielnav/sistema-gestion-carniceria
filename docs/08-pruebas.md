# 08 - Plan de pruebas

| Campo | Valor |
|---|---|
| Versión | 0.1 (borrador) |
| Base | Reglas de negocio (RN-xx) de [04-casos-de-uso.md](04-casos-de-uso.md), reglas de integridad (RI-xx) de [05-modelo-datos.md](05-modelo-datos.md) y requisitos de [03-requisitos.md](03-requisitos.md) |
| Herramientas | `pytest` con `pytest-django`, base de datos PostgreSQL de prueba (D-09, D-14) |
| Alcance | Estrategia, criterios y casos de prueba base. Los casos se detallan hito por hito, cuando se construye cada módulo |

> Convención: un caso de prueba marcado **(a confirmar)** depende de una brecha abierta (PR-xx). No se automatiza como regla definitiva hasta que el negocio la confirme.

## 1. Criterio general

El sistema lo mantiene una sola persona (RNF-13), por lo que la estrategia busca el mayor valor con el menor mantenimiento:

1. **Las reglas del negocio y de integridad se prueban automáticamente.** Es donde un error cuesta plata (caja, stock, saldos).
2. **Las pantallas se prueban a mano**, con una lista corta de recorridos, y con pruebas automáticas solo para permisos y flujos críticos.
3. **Toda regla RN-xx o RI-xx tiene al menos una prueba** (regla de [06-arquitectura.md](06-arquitectura.md), sección 7).
4. **Las pruebas nunca usan datos reales ni la base de desarrollo** (RNF-16, D-14).

## 2. Niveles de prueba

| Nivel | Qué verifica | Cómo | Cuándo |
|---|---|---|---|
| Integridad de base de datos | Restricciones `UNIQUE`, `CHECK`, claves foráneas (RI-xx) | `pytest` creando datos inválidos y esperando el rechazo de la base | Desde H1 |
| Servicios (reglas de negocio) | Cálculos y operaciones que tocan varias tablas (RN-xx, RNF-10) | `pytest` llamando a la capa de servicios, incluyendo que una falla a mitad deja todo sin cambios | En cada hito |
| Permisos por rol | Qué ve y qué puede hacer cada rol (RF-02, RN-05, RN-06) | `pytest` con el cliente de prueba de Django, por rol | Desde H1 |
| Vistas y formularios | Que la pantalla responde, valida y guarda | `pytest` con el cliente de prueba (flujos críticos) | En cada hito |
| JavaScript puro | Lógica del navegador sin pantalla, como la detección del lector (DEC-75) | `node --test` sobre `apps/*/tests/js/`, llamado desde `pytest`; se saltea si no hay Node | Desde H2 |
| Concurrencia | Que dos operaciones sobre la misma caja no se cruzan (RNF-10) | `pytest` con transacciones reales y dos hilos | Desde H2 |
| Recorridos manuales | Que lo construido se puede usar, en PC y celular (RNF-02, RNF-03) | Lista de recorridos de la sección 6 | Al cerrar cada hito |
| Aceptación | Que el negocio lo considera útil | Prueba con datos ficticios frente a la cajera y el administrador | Antes de la entrega (H6) |

No se prevén pruebas de carga ni de interfaz automatizadas (la unión de `venta.js` con `lector.js` y `buscador.js` se verifica en los recorridos con Playwright): no se justifican para un local con pocos usuarios simultáneos. Se reevalúa si aparece un problema de rendimiento (RNF-12, umbral a definir).

## 3. Entorno y datos de prueba

| Aspecto | Decisión |
|---|---|
| Base | PostgreSQL local, base separada de la de desarrollo; `pytest-django` la crea y la destruye en cada corrida |
| Credenciales | Exclusivas de desarrollo, definidas en el `.env` local (no se sube). Ver D-14 en [06-arquitectura.md](06-arquitectura.md) |
| Datos | Ficticios, cargados con un comando propio (H1.3) o creados dentro de cada prueba |
| Reloj | Las pruebas que dependen de fecha o turno fijan la fecha, para no depender del día en que se corren |
| Integración continua | GitHub Actions corre ruff, el control de migraciones y las pruebas con PostgreSQL 18 en cada Pull Request y en `main` (D-09, `.github/workflows/pruebas.yml`) |

## 4. Casos de prueba automáticos

Cada fila es un caso base. Al implementar el módulo se desglosan los casos (camino feliz, errores, límites) y se les asigna el ID definitivo en el código de prueba.

### 4.1 Caja (CU-02, CU-03)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-01 | Abrir caja de un turno sin caja abierta | RN-01, RF-04 | Se crea la caja en estado `ABIERTA` con la fecha de hoy, el turno elegido y la cajera | Confirmado; automatizado (H2, etapa 1) |
| CP-02 | Abrir una segunda caja del mismo turno y fecha | RN-01, RI-01, RF-05 | La base y el servicio la rechazan, con un mensaje que nombra la caja abierta | Confirmado; automatizado (H2, etapa 1) |
| CP-03 | Los turnos válidos son mañana y tarde | RN-02 | Un turno distinto es rechazado | Confirmado |
| CP-04 | Cerrar caja con montos contados | RF-07, RI-10 | La diferencia es `monto_contado - monto_sistema` y no se guarda | Confirmado; automatizado (H2, etapa 3) |
| CP-05 | Agregar una venta o un movimiento a una caja cerrada | RN-03, RI-02, RNF-09 | Se rechaza | Confirmado; automatizado (H2, etapa 3) |
| CP-06 | Cierre con diferencia distinta de cero | RF-09 | El sistema avisa y no cierra sin un motivo; con motivo, cierra sin autorización | Decidido (DEC-40); automatizado (H2, etapa 3) |
| CP-07 | Abrir caja con fondo de cambio | RF-10 | Se registra el monto inicial (opcional, en efectivo; vacío se guarda 0) y se suma al efectivo esperado del cierre | Decidido (DEC-38); apertura automatizada (H2, etapa 1) y suma en el cierre (H2, etapa 3) |
| CP-79 | Abrir la caja de la tarde con la de la mañana abierta | RI-01, CU-02 A3 | Se rechaza y pide cerrar la caja abierta | Decidido (DEC-39); automatizado (H2, etapa 1) |
| CP-80 | Abrir otra caja en un turno que ya tuvo una caja cerrada el mismo día | RI-01, CU-02 A4 | Se abre una caja nueva en ese turno y la cerrada sigue cerrada; sin caja abierta, el formulario ofrece los dos turnos | Decidido (DEC-83, reemplaza a DEC-39); automatizado (etapa 0b de H3) |
| CP-81 | Egreso "otro" (gasto o retiro en efectivo) | SC-02, RI-13 | Se registra con concepto `OTRO` y descripción obligatoria, y se resta del efectivo esperado; sin descripción se rechaza | Decidido (DEC-43); automatizado (H2, etapa 3) |

### 4.2 Ventas (CU-01)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-10 | Venta con varios productos | RF-12, RI-03 | `monto_total` es la suma de los subtotales de los detalles | Confirmado; automatizado (H2, etapa 2) |
| CP-11 | Venta en efectivo | RN-04, RI-04 | Genera un `movimiento_caja` de ingreso por el monto y el medio de pago, en la misma operación | Confirmado; automatizado (H2, etapa 2) |
| CP-12 | Venta con producto con control de stock | RF-16, RI-07 | El `stock_actual` baja la cantidad vendida | Confirmado (no cárnicos); automatizado (H2, etapa 2) |
| CP-13 | Venta con producto sin control de stock | RI-07 | El stock no cambia | Confirmado; automatizado (H2, etapa 2) |
| CP-14 | Falla a mitad de la venta (error forzado al registrar el movimiento de caja) | RNF-10 | No quedan venta, detalle, movimiento ni cambio de stock | Confirmado; automatizado (H2, etapa 2) |
| CP-15 | Cambiar el precio de un producto después de venderlo | RI-12 | La venta anterior conserva el precio original | Confirmado; automatizado (H2, etapa 2) |
| CP-16 | Cantidad cero o negativa, precio negativo | RI-16 | Se rechaza | Confirmado; automatizado (H2, etapa 2) |
| CP-17 | Venta sin caja abierta | CU-01 A4, RF-15 | Se rechaza con mensaje claro; también si la caja abierta es de otro día | Decidido (DEC-83, DEC-50); automatizado (H2, etapa 2) |
| CP-18 | Venta a cuenta corriente con cliente | RI-05, RF-18 | Genera `VENTA_FIADA` y no genera ingreso en caja | A confirmar (PR-12, PR-13) |
| CP-19 | Venta a cuenta corriente sin cliente | RI-05 | Se rechaza | A confirmar (PR-12) |
| CP-20 | Venta de carne | RF-20, RF-16 | Se registra por producto y por kg con su precio; el stock no cambia | Decidido (DEC-36); automatizado (H2, etapa 2) |
| CP-21 | Venta con más de un medio de pago | RF-19 | No se permite: un solo medio por venta | Decidido (DEC-42); automatizado (H2, etapa 2) |
| CP-82 | Buscar con el código del lector | RF-11 | Un código que coincide exacto con un plus agrega el producto a la venta | Decidido (DEC-37); automatizado (H2, etapa 2) |
| CP-106 | Ver y filtrar los productos desde el buscador de la venta | DEC-97, DEC-52 | Sin texto trae los activos por nombre, sin stock y hasta 50, avisando si hay más; "Ver productos" muestra todos aunque haya texto escrito; filtra al dejar de escribir; una lectura rápida terminada en Enter no filtra y agrega por plus exacto; una respuesta vieja no reabre la lista; las flechas no se salen de la lista | Decidido (DEC-97); automatizado (servicio, vista y `buscador.js` con `node --test`) |
| CP-83 | Venta con stock insuficiente | CU-01 A3, RI-07 | Se permite con aviso y el `stock_actual` queda negativo; el aviso también aparece al agregar el producto (CP-110) | Decidido (DEC-46); automatizado (H2, etapa 2) |
| CP-110 | Aviso de stock insuficiente al agregar a la venta | CU-01 A3, DEC-102, DEC-103 | Si la cantidad de la línea supera el stock de un producto con control, la pantalla avisa al agregarlo o al cambiar la cantidad; el aviso muestra la cantidad disponible, según la unidad, y también aparece si no hay stock; sin control de stock no avisa; la venta se confirma igual (DEC-46) | Decidido (DEC-102); automatizado (H3, etapa 5: datos en la vista y `aviso_stock.js` con `node --test`) |
| CP-84 | Ticket de una venta confirmada | RF-14 | Muestra negocio, número, fecha y hora, cajera, detalle, total, medio de pago y "No válido como factura" | Decidido (DEC-44); automatizado (H2, etapa 2) |
| CP-85 | Anular una venta | RI-02, RI-07 | Solo el Administrador, con motivo y con la caja abierta: la venta queda anulada y, en la misma operación, se registra un egreso `ANULACION` por su total y su medio y el stock de cada producto con control vuelve exactamente al valor previo a la venta (varias líneas, kg con decimales, producto creado durante la venta; los productos sin control no se tocan); el esperado del cierre la descuenta. Una segunda anulación se rechaza y no devuelve stock otra vez. El motivo admite hasta 255 caracteres. Se rechaza sin motivo, ya anulada, con la caja cerrada o si no alcanza el efectivo | Decidido (DEC-45, DEC-66 a DEC-70); automatizado (H2, etapa 4) |
| CP-87 | Cantidad por línea sobre el máximo | DEC-76 (supuesto, PR-36), DF-01 | Más de 100 kg o 100 unidades en una línea (ya agrupada) se rechaza; 100 se acepta. En la pantalla, Enter en el peso vuelve al buscador y una lectura del lector en el peso se busca como producto sin tocar la cantidad (DEC-75, prueba de `static/js/lector.js` con `node --test`) | Supuesto (DEC-76); automatizado (H2, etapa 4) |
| CP-88 | Venta o anulación y cierre de caja al mismo tiempo | RNF-10, RI-02 | Si el cierre toma la caja primero, la venta o la anulación espera y se rechaza (no queda venta en la caja cerrada ni se anula); si la venta va primero, el cierre espera y la incluye en lo esperado | Automatizado (H2, etapa 4; transacciones reales con dos hilos) |
| CP-89 | Cierre con ventas anuladas | DEC-77 | La pantalla de cierre y el reporte listan cada venta anulada con hora, número, motivo, monto y medio; sin anulaciones no aparece la lista | Automatizado (H2, etapa 4) |
| CP-94 | Venta en curso guardada en la pestaña | DEC-47 | Las líneas y el medio se guardan en `sessionStorage` por usuario y se recuperan al volver; una venta vacía, confirmada o vaciada no deja nada; datos dañados se ignoran y, sin almacenamiento, la venta funciona igual. Al salir con productos cargados el navegador avisa (se verifica en los recorridos) | Decidido (DEC-47); automatizado con `node --test` (etapa 0b de H3) |
| CP-95 | Ventas de la caja para la cajera | DEC-84, DEC-45 | La cajera ve la lista, el detalle y el ticket de las ventas de la caja abierta, sin "Anular venta" ni acceso al historial; si manda la anulación igual, recibe 403 y la venta no cambia. Los dueños reciben 403 | Decidido (DEC-84); automatizado (etapa 0b de H3) |
| CP-96 | Ticket y detalle de una venta de caja cerrada | DEC-84, L4 | La cajera recibe 403; el Administrador lo ve, sin "Nueva venta" | Decidido (DEC-84); automatizado (etapa 0b de H3) |
| CP-98 | Historial de ventas del Administrador | DEC-86, RF-49 | Por defecto trae la caja abierta (sin caja abierta, todas); filtra por fecha desde y hasta, turno y caja (también varias cajas del mismo turno); "Todas las ventas" ignora la caja abierta; desde posterior a hasta muestra el error; pagina de a 25 y conserva los filtros; abre detalle y ticket de cajas cerradas, pero no anula sus ventas. La cajera y los dueños reciben 403 | Decidido (DEC-86); automatizado (etapa 0b de H3) |

### 4.3 Stock, ingresos y proveedores (CU-05, CU-06, CU-07)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-30 | Ingreso de mercadería | RN-08, RF-23, RI-07 | El stock sube la cantidad ingresada | Confirmado; automatizado (H3, etapa 3) |
| CP-31 | Ingreso con precio de compra | RI-12 | Se guarda el precio en el detalle del ingreso | Confirmado; automatizado (H3, etapa 3) |
| CP-32 | Ingreso que genera deuda con el proveedor | RN-08, RF-30 | Un ingreso `A_CREDITO` aumenta el saldo del proveedor (calculado como ingresos menos pagos, no guardado); uno `CONTADO` no deja saldo | Decidido (DEC-81, supuesto); automatizado (H3, etapas 3 y 4) |
| CP-33 | Pago a proveedor menor o igual a la deuda | RF-31, RF-32 | El saldo baja | Confirmado; automatizado (H3, etapa 4) |
| CP-34 | Pagos de un ingreso que superan su total | RI-08 | Se rechaza | Confirmado; automatizado (H3, etapa 4) |
| CP-35 | Pago a proveedor con `ingreso_id` de otro proveedor | RI-14 | Se rechaza | Confirmado; automatizado (H3, etapa 4) |
| CP-36 | Pago a proveedor en efectivo sin disponibilidad | RN-09, RI-09, RF-33 | Si supera el efectivo esperado de la caja, se rechaza mostrando el máximo disponible; con un monto igual se acepta y genera el egreso `PAGO_PROVEEDOR` a nombre de quien registra, aunque la caja la haya abierto otro usuario | Decidido (DEC-80, supuesto); automatizado (H3, etapa 4) |
| CP-90 | Medio del pago a proveedor | RF-33, RI-13 | Por transferencia se registra sin movimiento de caja y sin validar disponibilidad; con cuenta corriente u otro medio se rechaza | Decidido (DEC-80, supuesto); automatizado (H3, etapa 4) |
| CP-91 | Pago a proveedor en efectivo sin caja abierta del día | RN-09 | Se rechaza si no hay caja abierta o si la abierta es de otro día | Decidido (DEC-80, supuesto); automatizado (H3, etapa 4) |
| CP-92 | Ingreso al contado | RN-08, RF-30, RNF-10 | Se guardan juntos el ingreso, el stock, el pago por el total y, si es en efectivo, el egreso; si el pago se rechaza (por ejemplo, por falta de efectivo), no se guarda nada | Decidido (DEC-81, supuesto); automatizado (H3, etapa 4) |
| CP-93 | Cantidades del ingreso | RF-22, RI-16 | Por `UNIDAD` se rechaza una cantidad con decimales; por `KG` se aceptan hasta 3 decimales; más de 100 kg o 100 unidades se acepta (no rige DEC-76) | Decidido (DEC-79, DEC-81, supuesto); automatizado (H3, etapa 3) |
| CP-37 | Stock en o por debajo del mínimo | RN-10, RF-26 | La consulta en `/productos/` (DEC-105), con filtros por categoría, proveedor y "Solo stock bajo", muestra la alerta si `stock_actual <= stock_minimo` y, sin mínimo, si `stock_actual <= 0` (DEC-101); sin mínimo y con stock mayor a 0, o en carne, no hay alerta. La tarjeta "stock bajo" del inicio la ve solo el Administrador | Decidido (DEC-82 y DEC-101, supuesto); automatizado (H3, etapa 5) |
| CP-100 | Precio de compra sugerido y actualizado | DEC-90, RI-12 | El ingreso precarga el último precio de compra del producto con ese proveedor y, al confirmar, lo crea o actualiza; anular el ingreso no lo revierte | Decidido (DEC-90); automatizado (H3, etapa 3) |
| CP-101 | Anular un ingreso | DEC-92, RI-07 | Solo el Administrador, con motivo y sin pagos vigentes: el ingreso queda anulado, el stock vuelve (aunque quede negativo) y el saldo del proveedor baja; con un pago vigente, se rechaza | Decidido (DEC-92); automatizado (H3, etapa 3) |
| CP-102 | Anular un pago a proveedor | DEC-92, RI-13 | Solo el Administrador, con motivo: por transferencia, sin movimiento de caja; en efectivo con su caja abierta, una reversa `INGRESO` `ANULACION_PAGO` vinculada al pago, sin tocar el egreso; con la caja cerrada, se rechaza; un pago tiene a lo sumo una reversa. El saldo vuelve a subir | Decidido (DEC-92); automatizado (H3, etapa 4) |
| CP-112 | Pago a proveedor al mismo tiempo que el cierre de caja o que la anulación del ingreso | RNF-10, RI-02, RI-08 | Si el cierre toma la caja primero, el pago en efectivo espera y se rechaza; si el pago va primero, el cierre espera y lo incluye en lo esperado; si la anulación del ingreso va primero, el pago espera y se rechaza | Automatizado (H3, etapa 4; transacciones reales con dos hilos, como CP-88) |
| CP-113 | Flujo completo de H3 | RF-22, RF-23, RF-25, RF-31, RF-33, RN-08, RN-09, RN-10 | Proveedor, ingreso a crédito, venta con aviso de stock, tarjeta "Stock bajo", pago en efectivo y cierre de caja, por las pantallas y con dos roles: el stock, el saldo y lo esperado coinciden, y el cierre lista el pago | Automatizado (H3, etapa 6) |
| CP-107 | Cambiar el stock al modificar un producto | RF-50, RI-07, RI-17, DEC-98 | El Administrador cambia el stock en `/productos/` o en el panel: el stock queda en el valor cargado y se registra el ajuste con usuario, fecha, anterior, nuevo y el motivo elegido (por defecto "Modificación manual"); sin cambio no hay ajuste; una venta hecha mientras se editaba no se deshace; negativo, con decimales por `UNIDAD` o con más de 3 decimales se rechaza junto al campo; sin control de stock no se cambia; solo el Administrador | Decidido (DEC-98, supuesto); automatizado (H3, etapa 1b) |

### 4.4 Clientes y cuentas corrientes (CU-04, CU-08)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-40 | Pago de cliente menor o igual a la deuda | RF-36, RF-37, RN-04 | El saldo baja y se registra el ingreso en caja | Confirmado |
| CP-41 | Pago de cliente mayor a la deuda | RN-07, RI-06, RF-38 | El excedente se registra como `ANTICIPO` | A confirmar (PR-15) |
| CP-42 | El saldo del cliente se calcula desde los movimientos | DEC-21 | Saldo = ventas fiadas - pagos; no hay saldo guardado | Confirmado |
| CP-43 | Movimiento de cuenta corriente de otro cliente que la venta | RI-15 | Se rechaza | Confirmado |
| CP-44 | Cliente con deuda vencida | RN-11, RF-40 | Muestra alerta | A confirmar (PR-13) |

### 4.5 Productos, usuarios y permisos (CU-10 a CU-14)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-50 | Inicio de sesión correcto e incorrecto | RF-01 | Entra con credenciales válidas; con inválidas o dado de baja, no, con un mensaje genérico (CU-10 A1, A2) | Confirmado |
| CP-51 | La contraseña no se guarda en texto plano | RNF-07 | En la base figura el hash | Confirmado |
| CP-52 | Usuario sin sesión accede a una pantalla | RNF-06 | Redirige al inicio de sesión | Confirmado |
| CP-53 | Dueños intentan crear o modificar datos | RN-06, RF-45 | Se rechaza (403 en las pantallas, sin acceso al panel); sí pueden ver reportes | Confirmado |
| CP-54 | Cajera accede a funciones de administrador | RF-02 | Se rechaza (403 en las pantallas, sin acceso al panel) | Confirmado |
| CP-55 | Cajera sin permiso crea un producto | RN-05 | Se rechaza en el servicio, en la pantalla y por URL directa (403); sí consulta el listado y el stock (DEC-103) | Confirmado |
| CP-56 | Cajera con permiso crea un producto durante la venta | RN-05, RF-17 | Se crea. En H1 se prueba desde la pantalla de productos; desde la venta (`/ventas/producto/`), en H2: el producto se agrega a la venta en curso, y sin permiso la opción no aparece y el alta da 403. La cajera con permiso no modifica ni da de baja | Confirmado; automatizado (H1 y H2, etapa 4) |
| CP-57 | Baja de un producto con ventas | RI-11 | Baja lógica: el producto queda inactivo y las ventas siguen intactas; deja de listarse salvo con el filtro del Administrador y no se edita desde la pantalla ni por su URL (DEC-33) | Confirmado |
| CP-97 | Reactivar un producto dado de baja | DEC-85, CU-11 | El Administrador lo reactiva con "Reactivar" en el listado de dados de baja (POST), sin condición de stock; la cajera y los dueños reciben 403 y un producto activo da 404 | Decidido (DEC-85); automatizado (etapa 0b de H3) |
| CP-108 | Stock inicial en el alta de un producto | RF-51, DEC-99, DEC-103 | El Administrador da de alta un producto con control de stock y stock 12 (en `/productos/` o en el panel): el stock queda en 12 y se registra un ajuste "Stock inicial" con anterior 0; sin valor, arranca en 0 sin ajuste; sin control de stock se rechaza junto al campo; la cajera con permiso no ve el campo y su alta arranca en 0 | Decidido (DEC-99, supuesto); automatizado (H3, etapa 1b) |
| CP-111 | La cajera consulta productos y stock | DEC-103, RF-25 | Toda cajera, con o sin permiso de alta, ve `/productos/` con el stock y el mínimo en solo lectura, sin "Editar", "Dar de baja" ni el filtro de dados de baja; solo la cajera con permiso ve "Nuevo producto"; editar y dar de baja por URL dan 403; los dueños no acceden | Decidido (DEC-103); automatizado (H3, etapa 1b) |
| CP-58 | Intentar borrar un registro referenciado | RI-11 | La aplicación y la base lo impiden (la prueba fuerza el control inmediato de las claves foráneas, que en Django son diferidas) | Confirmado |
| CP-59 | Plus interno de producto repetido (si no es nulo) y nombre de usuario repetido | `UNIQUE` de `producto` y `usuario` en la sección 7 de [05-modelo-datos.md](05-modelo-datos.md) | Se rechaza; en producto, con el mensaje junto al campo (CU-11 A1), también si otra operación guarda el mismo plus al mismo tiempo | Confirmado para `usuario`; `producto` implementado con el supuesto de 05 (único si existe), a confirmar (PR-22; el plus, DEC-37) |
| CP-99 | Gestionar proveedores | RF-29, DEC-87, DEC-88 | El Administrador da de alta, modifica, da de baja (con confirmación) y reactiva un proveedor; un proveedor dado de baja no se lista salvo con el filtro; la cajera y los dueños reciben 403 | Decidido (DEC-87); automatizado (H3, etapa 2), con la prueba de estructura de R-6 |
| CP-103 | Registros operativos en el panel de administración | DEC-31 | Ventas, ingresos, cajas, pagos y movimientos se consultan, pero el alta, la modificación y el borrado responden 403 y el registro no cambia | Automatizado |
| CP-104 | Ficha de una venta y de un ingreso en el panel | DEC-31, DEC-67 | La venta muestra el bloque "Venta" con etiquetas claras y el bloque "Anulación" solo si está anulada; los productos de la venta y del ingreso se ven dentro como tabla de solo lectura, y los detalles no tienen listado propio ni título por renglón; las cantidades se leen "2" o "1,250 kg" (DEC-48) | Automatizado |
| CP-105 | Grupos y permisos individuales en el panel | DEC-32 | No existe la página de Grupos y la ficha del usuario no muestra `groups` ni `user_permissions` | Automatizado |
| CP-109 | Producto y ajustes en el panel de administración | DEC-100, DEC-31 | El panel da de alta y modifica productos con el servicio de catálogo: el stock editado se valida igual que en `/productos/` y registra el ajuste; `ajuste_stock` se consulta pero no se crea, modifica ni borra | Decidido (DEC-100); automatizado (H3, etapa 1b) |

### 4.6 Reportes (CU-09)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-60 | Reporte de ventas por rango de fechas | RF-42, RF-43 | Los totales coinciden con las ventas del rango | Confirmado |
| CP-61 | Totales por medio de pago | RF-42 | La suma por medio coincide con el total | Confirmado |
| CP-62 | Período sin datos | RF-44 | Muestra "Sin registros disponibles" | Confirmado |
| CP-63 | Exportar a PDF y a Excel | RF-43 | El archivo se genera y los montos coinciden con la pantalla | Confirmado |

### 4.7 Integridad general de la base de datos

| ID | Caso | Regla | Resultado esperado |
|---|---|---|---|
| CP-70 | `movimiento_caja` con ninguna o más de una referencia a venta/pago | RI-13 | La base rechaza el registro. Una `ANULACION` sin venta, como ingreso o repetida para la misma venta también se rechaza (DEC-68) |
| CP-86 | `venta` con estado inválido o con datos de anulación que no coinciden con el estado | DEC-67 | La base rechaza el registro |
| CP-71 | Montos negativos y cantidades menores o iguales a cero en la base | RI-16 | La base los rechaza (restricción `CHECK`, no solo validación de formulario) |
| CP-72 | Migraciones sobre base vacía | H1.2 | Se aplican sin errores, no quedan migraciones sin aplicar y los modelos no tienen cambios sin migrar |
| CP-73 | Las entidades existen con sus claves y restricciones | [05-modelo-datos.md](05-modelo-datos.md) | Coincide con el modelo: las 17 tablas (18 desde `ajuste_stock`, etapa 1b de H3, DEC-98) y ninguna condicional, auditoría en todas, cada `CHECK` y `UNIQUE` de la sección 7.4 (los parciales, con su condición), los índices de la sección 7.5 y toda clave foránea con `PROTECT` |
| CP-74 | Menú de la plantilla base por rol | RF-02, RN-05 (H1.4) | Administrador: historial de ventas (con anulación, DEC-71, DEC-86), productos (con la consulta de stock, DEC-105), clientes, proveedores, reportes y usuarios; cajera: ventas, ventas de la caja (sin anular, DEC-84), caja y productos, con o sin permiso de alta (DEC-103); dueños: solo reportes |
| CP-75 | Abrir el inicio sin sesión | RF-01, RNF-06 (H1.4) | Redirige al ingreso |
| CP-76 | Resumen del día en el inicio | H1.4 (DEC-30) | Ventas de hoy (cantidad y monto, sin las de otros días ni las anuladas, DEC-73), cajas abiertas, productos activos y últimas ventas salen de la base |
| CP-77 | Cargar los datos de ejemplo dos veces | H1.3 | No se duplica nada; hay un usuario por rol, una cajera con permiso de alta y otra sin él, y cada uno entra con la contraseña de `DEMO_PASSWORD`; fuera de desarrollo o sin esa variable el comando no corre |
| CP-78 | Usuario que no es Administrador con acceso al panel o como superusuario | DEC-32 | La base lo rechaza |

## 5. Trazabilidad de reglas a pruebas

Toda regla debe tener al menos una prueba. Si se agrega una regla, se agrega su fila.

| Regla | Casos | Regla | Casos |
|---|---|---|---|
| RN-01 | CP-01, CP-02, CP-79 | RI-01 | CP-02, CP-79, CP-80 |
| RN-02 | CP-03 | RI-02 | CP-05, CP-85 |
| RN-03 | CP-05 | RI-03 | CP-10 |
| RN-04 | CP-11, CP-40 | RI-04 | CP-11 |
| RN-05 | CP-55, CP-56, CP-74 | RI-05 | CP-18, CP-19 |
| RN-06 | CP-53 | RI-06 | CP-41 |
| RN-07 | CP-41 | RI-07 | CP-12, CP-13, CP-30, CP-85, CP-107 |
| RN-08 | CP-30, CP-32, CP-92 | RI-08 | CP-34 |
| RN-09 | CP-36, CP-91 | RI-09 | CP-36 |
| RN-10 | CP-37 | RI-10 | CP-04 |
| RN-11 | CP-44 | RI-11 | CP-57, CP-58 |
| RNF-07 | CP-51 | RI-12 | CP-15, CP-31 |
| RNF-09 | CP-05 | RI-13 | CP-70 |
| RNF-10 | CP-14, CP-85, CP-88 | RI-14 | CP-35 |
| — | — | RI-15 | CP-42, CP-43 |
| — | — | RI-16 | CP-16, CP-71 |
| — | — | RI-17 | CP-107, CP-108 |

## 6. Recorridos manuales

Se ejecutan al cerrar cada hito, en Chrome de PC y en un celular. Cada recorrido se anota con fecha y resultado (OK / falla / observación).

| ID | Recorrido | Hito | Rol |
|---|---|---|---|
| RM-01 | Iniciar sesión, ver el menú propio del rol y cerrar sesión | H1 | Los tres |
| RM-02 | Crear, editar y dar de baja un producto | H1 | Administrador |
| RM-03 | Abrir caja, registrar tres ventas con distintos medios de pago y cerrar caja con diferencia | H2 | Cajera |
| RM-04 | Registrar una venta en pocos pasos, con lector de códigos o búsqueda (RNF-03) | H2 | Cajera |
| RM-05 | Registrar un ingreso de mercadería y ver el stock actualizado y la alerta de mínimo | H3 | Administrador |
| RM-06 | Registrar un pago a proveedor y ver el saldo | H3 | Administrador |
| RM-10 | Flujo completo de H3: proveedor, producto, ingreso a crédito, venta con aviso de stock, tarjeta "Stock bajo", pago en efectivo y cierre de caja | H3 | Administrador / Cajera |
| RM-07 | Vender a cuenta corriente, registrar un pago y ver el estado de cuenta | H4 | Administrador / Cajera |
| RM-08 | Generar un reporte, exportarlo y comparar sus totales con la caja | H5 | Administrador / Dueños |
| RM-09 | Usar el sistema desde el celular en todas las pantallas anteriores | H6 | Los tres |

### Registro de recorridos

| Fecha | Recorrido | Resultado | Observaciones |
|---|---|---|---|
| 2026-10-22 | RM-01 | OK | En local con los usuarios de ejemplo (H1.3), en PC y en tamaño de celular (375 px). Clave equivocada: mensaje genérico. Administrador: productos, stock, clientes, proveedores, reportes, usuarios y el panel. Cajera con permiso: ventas, caja y productos. Cajera sin permiso: ventas y caja; el panel le pide ingresar de nuevo. Dueño: reportes. Las funciones sin pantalla aparecen deshabilitadas ("Pronto"). Los cuatro salen y vuelven al ingreso. Recorrido confirmado por el alumno: hecho |
| 2026-10-22 | RM-02 | OK | En local con los usuarios de ejemplo. Administrador: alta de un producto de prueba (plus 990), edición del precio, plus repetido rechazado con el mensaje junto al campo, baja con confirmación; el producto deja de listarse y aparece "Dado de baja" con el filtro "Incluir dados de baja", sin opción de reactivar. Cajera con permiso: listado sin stock, sin Editar, sin Dar de baja y sin el filtro; alta de un producto (plus 991); la URL de edición responde "Sin permiso". Cajera sin permiso: el menú no muestra Productos y `/productos/` y `/productos/nuevo/` responden "Sin permiso" (CP-55). Recorrido hecho por el agente en el navegador; validado por el alumno |
| 2026-10-26 | RM-03 | OK | En local con los datos de ejemplo, como cajera. Se cerró la caja de la mañana del 25/10 (dos ventas del día anterior y un retiro de $ 2.000): esperado en efectivo $ 22.250, contado $ 22.000; sin motivo no cerró y con motivo cerró. Después se abrió la mañana del 26/10 con fondo de $ 3.000, se registraron tres ventas con efectivo (vacío por kg), tarjeta y QR, y se cerró contando $ 100 de más con su motivo. Los reportes de cierre muestran esperado, contado, diferencia, egresos y motivo; el Administrador y los dueños ven el reporte y reciben 403 en Caja y en el cierre. Recorrido hecho en el navegador con Playwright |
| 2026-10-26 | Etapa 4 de H2 (CU-01 A1 y DEC-45) | OK | En local con los datos de ejemplo. Cajera con permiso: con 1,5 kg de asado cargado, buscó "Matambre de cerdo", tocó "Crear producto" (nombre precargado), el plus 101 repetido se rechazó junto al campo, con otro plus se creó y se agregó a la venta con el cursor en la cantidad; la venta se confirmó con las dos líneas. Cajera sin permiso: sin "Crear producto" y 403 en el alta directa. Administrador: "Ventas del turno" lista la caja abierta; sin motivo la anulación se rechaza; con motivo y confirmación, la venta de 2 carbones ($ 11.000, efectivo) quedó anulada, el egreso `ANULACION` se registró, el stock volvió de 7 a 9, el efectivo esperado del cierre bajó de $ 34.950 a $ 23.950 y el inicio dejó de contarla y la marca como anulada. Observación: el navegador tenía en caché el `venta.js` anterior y no mostraba el botón hasta recargarlo sin caché. Recorrido hecho en el navegador con Playwright |
| 2026-10-26 | RM-04 | OK con observaciones | En local con los datos de ejemplo, como cajera, en la caja de la tarde del 26/10. PC (1280 px): la pantalla abre con el cursor en el buscador; con el lector simulado (código y Enter) "601" agregó la gaseosa y el cursor volvió al buscador, otro "601" sumó 2 en la misma línea (DEC-53), "101" agregó el asado con el cursor en la cantidad (DEC-52); "pollo" con Enter mostró la lista y al elegir la pechuga quedó el cursor en el peso. Venta 11: 3 líneas, $ 22.150, efectivo, ticket correcto, en unos 2 segundos de acciones y sin recargar la página. Celular (375 px): venta 12 (agua por lector, vacío por búsqueda, QR, $ 13.000) confirmada con ticket. Observaciones: DF-01 y DF-02 (sección 8). Además, después de cargar un peso, Enter no vuelve al buscador: hay que tocarlo o usar Shift+Tab. Recorrido hecho en el navegador con Playwright |
| 2026-10-26 | RM-04 (pasos de DF-01 y DF-02) | OK | Repetidos después de la corrección, recargando sin caché. PC: peso tecleado y Enter deja el cursor en el buscador; "101", peso 0,750 y lectura "601" sin volver al buscador: la gaseosa se agrega y el asado sigue en 0,750 kg; "102", peso 1 y lectura "601": el vacío sigue en 1 kg. Un pedido directo con 1601 kg lo rechaza el servidor (DEC-76). Celular (375 px): la página mide 375 px y la tabla se desplaza dentro de su recuadro. Hecho con Playwright |
| 2026-10-30 | RM-05 | OK | En local, con Administrador temporal y datos temporales que se borraron al terminar. Ingreso de 5 unidades a $ 1.000: stock 5, saldo del proveedor $ 5.000 y alerta de mínimo en el listado al bajar el stock |
| 2026-10-30 | RM-06 | OK | Mismo recorrido. Pago de $ 5.000 en efectivo con $ 22.000 disponibles en la caja abierta por la cajera: saldo del ingreso en 0 y egreso a nombre del Administrador |
| 2026-10-30 | RM-10 | OK | Mismo recorrido. Caja con fondo de $ 10.000; venta de 6 unidades con stock 5: aviso "disponible 5" en la pantalla y en el ticket, stock -1. Tarjeta "Stock bajo" con 2 productos, que lleva al listado filtrado. Cierre: esperado en efectivo $ 17.000, contado igual, diferencia 0 y el pago listado en la pantalla y en el reporte. Sin errores |

## 7. Criterios de aceptación por hito

Un hito se da por terminado cuando:

1. Las pruebas automáticas de sus casos (no marcados "a confirmar") pasan.
2. Los recorridos manuales del hito se hicieron y no tienen fallas abiertas.
3. Las reglas del hito tienen su fila en la trazabilidad de la sección 5.
4. La documentación afectada de `/docs` está actualizada (ver [07-planificacion.md](07-planificacion.md)).
5. El cambio está en una rama con Pull Request, sin datos reales ni credenciales (RNF-16).

## 8. Registro de defectos

Para un proyecto individual alcanza con **GitHub Issues**, con las etiquetas `bug` y la del hito. Cada issue indica: pasos para reproducir, resultado obtenido, resultado esperado y caso de prueba (CP o RM) que lo detectó. Un defecto corregido debe sumar una prueba automática que lo cubra.

### Defectos detectados en los recorridos

| ID | Detectado en | Pasos | Obtenido | Esperado | Estado |
|---|---|---|---|---|---|
| DF-01 | RM-04 (2026-10-26) | En la venta, escanear un producto por kg ("101"), cargar el peso y escanear el siguiente producto sin volver al buscador | El código se escribe en la cantidad del producto anterior: 0,750 pasa a 0,750601 kg y no se agrega el producto. Con 3 decimales lo rechaza el servidor (DEC-48), pero un peso entero ("1" y luego "601") queda en 1601 kg y se acepta | Que el código del lector no termine en la cantidad: por ejemplo, que Enter en el peso vuelva al buscador, o que el lector se detecte en cualquier campo | **Corregido** (2026-10-26, etapa 4 de H2): Enter en el peso vuelve al buscador y una lectura en el peso se busca como producto sin tocar la cantidad (DEC-75); el servidor rechaza más de 100 kg o unidades por línea (DEC-76, supuesto). Pruebas: CP-87. Verificado de nuevo con Playwright, sin caché |
| DF-02 | RM-04 (2026-10-26) | Abrir `/ventas/nueva/` a 375 px de ancho y agregar productos | La tabla de la venta ensancha toda la página a unos 634 px y aparece desplazamiento horizontal; el encabezado queda angosto | La tabla se desplaza dentro de su recuadro y la página no se corre de costado (RNF-03; celular en H6, RM-09) | **Corregido** (2026-10-26, etapa 4 de H2). Dos causas: la grilla no limitaba el ancho de su columna (`grid-cols-1` y `min-w-0`) y el texto oculto "Quitar" (`sr-only`, posición absoluta) se escapaba del recorte del recuadro (`relative`). Lo mismo se aplicó a "Ventas del turno". Prueba de pantalla en `test_pantalla_ventas.py`; a 375 px la página mide 375 px y la tabla se desplaza sola (Playwright, sin caché) |
| DF-03 | Revisión de H3 (2026-10-30) | Confirmar un ingreso al contado en efectivo al mismo tiempo que una venta de los mismos productos, o con los productos en otro orden | Las dos operaciones se pueden trabar y una termina con error: el contado tocaba el stock antes de bloquear la caja y los productos no se bloqueaban en un orden fijo | El mismo orden en todas: caja y después productos por id | Corregido; prueba del orden en el contado |
| DF-04 | Revisión de H3 (2026-10-30) | Enviar al ingreso una cantidad o un precio enormes, o un filtro con un dígito como "²" | Error 500 | Mensaje claro o filtro ignorado | Corregido, con pruebas |

## 9. Pendientes que afectan las pruebas

| Pendiente | Efecto |
|---|---|
| PR-12, PR-13 (crédito y vencimiento) | CP-18, CP-19, CP-44 |
| PR-15 (excedente de pago) | CP-41 |
| PR-22 (unicidad de productos) | CP-59 |
| PR-37 (registro de faltantes de stock) | RF-27 no tiene prueba: mientras tanto se prueba el supuesto DEC-46 (CP-83) |
| PR-36 (máximo por línea) | CP-87 prueba el supuesto DEC-76 (100 kg o unidades); se ajusta al responder |
| Unión de `venta.js` con `lector.js` y `buscador.js` | No hay prueba de navegador automatizada: se verifica en los recorridos con Playwright. Agregarla implica una dependencia nueva (por ejemplo, pytest-playwright) y se decide aparte |
| RNF-12 (umbral de rendimiento) | No hay prueba de rendimiento hasta definirlo |
| Tablas con texto `sr-only` en otras pantallas (DF-02) | `catalogo/productos.html` (H1) tiene el mismo patrón que causó DF-02; verificar a 375 px en RM-09 (H6) o antes |
| Versionado de archivos estáticos (06, sección 9) | Hasta publicarse con nombres versionados, un recorrido puede usar un JavaScript viejo en caché: recargar sin caché antes de probar |

## 10. Mantenimiento

Al confirmar una brecha, se cambia el estado del caso a `Confirmado` y se automatiza. Al cambiar un requisito (03), un caso de uso (04) o una regla del modelo (05), se revisan los casos de esta página y la trazabilidad de la sección 5.
