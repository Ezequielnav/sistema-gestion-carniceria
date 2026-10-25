# 03 - Requisitos

| Campo | Valor |
|---|---|
| Versión | 0.1 (borrador) |
| Base | Relevamiento real ya realizado y casos de uso del documento base |
| Relacionados | [02-alcance-objetivos.md](02-alcance-objetivos.md), [04-casos-de-uso.md](04-casos-de-uso.md), [01-relevamiento.md](01-relevamiento.md) |

## 1. Convenciones

- **IDs:** RF-xx (requisitos funcionales) y RNF-xx (no funcionales). No se reutilizan IDs.
- **Origen:** `Base` indica que surge del documento de relevamiento (con la sección o caso de uso); `Propuesta` indica que lo agrega el análisis.
- **Prioridad** (propuesta, a validar con el responsable): `Alta` = necesario para operar; `Media` = importante; `Baja` = deseable.
- **Estado:** `Confirmado` = respaldado por el relevamiento base; `A confirmar` = depende de una brecha abierta (PR-xx) y no debe implementarse como regla de negocio hasta resolverse.
- **Casos de uso:** CU-01 a CU-09 se numeran según el documento base (venta, abrir caja, cerrar caja, pago de cliente, ingreso de mercadería, stock, pago a proveedor, cuentas corrientes, reportes). CU-10 a CU-14 son propuestos (inicio de sesión y gestión de productos, clientes, proveedores y usuarios). Detalle en [04-casos-de-uso.md](04-casos-de-uso.md).

## 2. Requisitos funcionales

### 2.1 Acceso y usuarios

| ID | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|
| RF-01 | El sistema debe permitir el inicio de sesión de los usuarios | Base (CU-02, precondición) | Alta | Confirmado |
| RF-02 | El sistema debe aplicar permisos según el rol: Administrador (acceso completo), Cajera (ventas, pagos, caja, alta de productos con permiso) y Dueños (solo consulta de reportes) | Base (2.2) | Alta | Confirmado |
| RF-03 | El Administrador debe poder crear, modificar y dar de baja usuarios y asignarles un rol | Propuesta (H-04) | Media | A confirmar (PR-25, PR-26) |

### 2.2 Caja

| ID | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|
| RF-04 | La cajera debe poder abrir la caja de un turno (mañana o tarde); se registra fecha, turno, empleado y estado "Abierta" | Base (CU-02) | Alta | Confirmado |
| RF-05 | El sistema no debe permitir abrir una segunda caja para un turno que ya tiene una caja abierta | Base (CU-02, A1) | Alta | Confirmado |
| RF-06 | El sistema debe registrar los ingresos y egresos de caja diferenciados por medio de pago | Base (2.1) | Alta | Confirmado |
| RF-07 | Al cerrar la caja, el sistema debe mostrar el resumen por medio de pago, permitir ingresar los montos contados y calcular las diferencias | Base (CU-03) | Alta | Confirmado |
| RF-08 | Al cerrar la caja, el sistema debe generar el reporte de cierre y bloquear la caja para edición | Base (CU-03) | Alta | Confirmado |
| RF-09 | El sistema debe definir qué ocurre ante una diferencia de caja (aviso, motivo, autorización) | Propuesta (H-12) | Media | Decidido (DEC-40): aviso y motivo obligatorio si hay diferencia, sin autorización |
| RF-10 | El sistema debe permitir registrar un monto inicial (fondo de cambio) al abrir la caja | Propuesta | Media | Decidido (DEC-38): opcional, en efectivo; si se deja vacío se guarda 0 |

### 2.3 Ventas

| ID | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|
| RF-11 | La cajera debe poder registrar una venta buscando o escaneando productos e indicando cantidades; el sistema muestra descripción, precio unitario y subtotal acumulado | Base (CU-01) | Alta | Confirmado |
| RF-12 | El sistema debe calcular el total de la venta | Base (CU-01) | Alta | Confirmado |
| RF-13 | La cajera debe poder seleccionar el medio de pago de la venta. Medios mencionados: efectivo, tarjeta, transferencia, QR y cuenta corriente | Base (2.1, CU-01) | Alta | Confirmado; lista decidida (DEC-41) |
| RF-14 | El sistema debe emitir un ticket o comprobante al confirmar la venta | Base (CU-01) | Alta | Confirmado; contenido decidido (DEC-44) |
| RF-15 | Al confirmar una venta, el sistema debe registrar el monto y el medio de pago en la caja abierta | Base (CU-01) | Alta | Confirmado |
| RF-16 | Al confirmar una venta, el sistema debe descontar el stock de los productos con control de stock | Base (CU-01) | Alta | Confirmado para no cárnicos; la carne no descuenta stock (DEC-36) |
| RF-17 | Si el producto no existe en el catálogo, la cajera con permiso debe poder crearlo durante la venta | Base (CU-01, A1) | Media | Confirmado |
| RF-18 | El sistema debe permitir vender a cuenta corriente asociando la venta a un cliente | Base (2.1, CU-08) | Alta | A confirmar (PR-12, PR-13) |
| RF-19 | El sistema debe permitir pagar una venta con más de un medio de pago | Propuesta (H-09) | Baja | Descartado (DEC-42): un solo medio por venta |
| RF-20 | El sistema debe registrar la venta de carne con el nivel de detalle que defina el negocio | Propuesta (H-01) | Alta | Decidido (DEC-36): por producto y por kg |

### 2.4 Productos y stock

| ID | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|
| RF-21 | El sistema debe gestionar el catálogo de productos (alta, baja, modificación) con nombre, precio, categoría, unidad de medida y plus interno | Propuesta (H-04, H-09) | Alta | A confirmar (PR-03, PR-22); plus decidido (DEC-37) |
| RF-22 | El Administrador debe poder registrar el ingreso de mercadería seleccionando proveedor, productos, cantidades y precio unitario | Base (CU-05) | Alta | Confirmado |
| RF-23 | Al confirmar un ingreso de mercadería, el sistema debe actualizar el stock | Base (CU-05) | Alta | Confirmado |
| RF-24 | Si un producto del ingreso no existe, el sistema debe permitir crearlo | Base (CU-05, A1) | Media | Confirmado |
| RF-25 | El Administrador debe poder consultar el stock de todos los productos y filtrar por categoría y proveedor | Base (CU-06) | Alta | Confirmado |
| RF-26 | El sistema debe mostrar alertas de stock mínimo en la consulta de stock | Base (CU-06) | Media | Confirmado (umbrales: PR-20) |
| RF-27 | El sistema debe permitir registrar un faltante de stock detectado | Base (diagrama de CU-01) | Baja | A confirmar |
| RF-28 | El sistema debe controlar los vencimientos de productos | Base (beneficio esperado) | Baja | A confirmar (PR-21) |

### 2.5 Proveedores

| ID | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|
| RF-29 | El Administrador debe poder gestionar proveedores (alta, baja, modificación, datos de contacto) | Propuesta (CU-05, precondición "proveedor registrado") | Alta | Confirmado en la necesidad; datos a detallar |
| RF-30 | Al ingresar mercadería, el sistema debe generar el registro de deuda o pago al proveedor | Base (CU-05) | Alta | Confirmado (modalidad: PR-18) |
| RF-31 | El Administrador debe poder registrar pagos a proveedores con proveedor, monto, fecha, medio de pago y productos asociados | Base (2.1, CU-07) | Alta | Confirmado |
| RF-32 | El sistema debe listar los proveedores con deudas pendientes y actualizar su saldo al registrar un pago | Base (CU-07) | Alta | Confirmado |
| RF-33 | Cuando el pago a proveedor sale de la caja, el sistema debe validar la disponibilidad y registrar el egreso; si el monto supera el saldo, debe advertir el máximo disponible | Base (CU-07, A1) | Media | A confirmar (PR-17, H-06) |
| RF-34 | El sistema debe permitir gestionar pedidos a proveedores | Propuesta (H-07) | Baja | A confirmar (PR-19) |

### 2.6 Clientes y cuentas corrientes

| ID | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|
| RF-35 | El sistema debe permitir gestionar clientes (alta, baja, modificación) | Propuesta (H-04) | Alta | A confirmar (PR-11) |
| RF-36 | El Administrador debe poder registrar el pago de un cliente de cuenta corriente: ver saldo, ingresar monto y medio de pago | Base (CU-04) | Alta | Confirmado (quién cobra: PR-14) |
| RF-37 | Al registrar un pago de cliente, el sistema debe disminuir el saldo adeudado y registrar el ingreso en caja | Base (CU-04) | Alta | Confirmado |
| RF-38 | Si el pago supera la deuda, el sistema debe sugerir registrar el excedente como anticipo | Base (CU-04, A1) | Baja | A confirmar (PR-15) |
| RF-39 | El Administrador debe poder consultar el estado de cuenta de un cliente: saldo, ventas fiadas y pagos realizados | Base (CU-08) | Alta | Confirmado |
| RF-40 | El sistema debe mostrar una alerta cuando un cliente tenga deuda vencida | Base (CU-08) | Media | A confirmar (PR-13) |
| RF-41 | El Administrador debe poder editar límites y condiciones de crédito de un cliente, si tiene permiso | Base (CU-08) | Media | A confirmar (PR-12, PR-16) |

### 2.7 Reportes

| ID | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|
| RF-42 | El sistema debe generar reportes de ventas diarias, producto más vendido, ingresos por día y totales por medio de pago | Base (2.1, CU-09) | Alta | Confirmado (lista final: PR-27) |
| RF-43 | El usuario debe poder indicar rango de fechas y formato de exportación (PDF o Excel) y descargar el reporte | Base (CU-09) | Media | Confirmado |
| RF-44 | Si no hay datos en el período, el sistema debe mostrar "Sin registros disponibles" | Base (CU-09, A1) | Baja | Confirmado |
| RF-45 | Los Dueños deben poder consultar los reportes sin modificar datos operativos | Base (2.2) | Alta | Confirmado |
| RF-46 | El sistema debe generar reportes de ventas y stock automáticamente al finalizar cada jornada | Base (meta) | Media | A confirmar (PR-27) |

### 2.8 Datos iniciales

| ID | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|
| RF-47 | El sistema debe permitir cargar datos históricos desde las planillas actuales | Propuesta | Baja | A confirmar (PR-28) |

## 3. Requisitos no funcionales

| ID | Categoría | Requisito | Origen | Prioridad | Estado |
|---|---|---|---|---|---|
| RNF-01 | Plataforma | El sistema debe ser una aplicación web accesible desde un navegador, con Google Chrome como navegador principal | Base (2.3) | Alta | Confirmado |
| RNF-02 | Portabilidad | La interfaz debe ser responsive y usable en PC, celular y tablet; el uso principal es desde PC de escritorio | Base (1.2, 2.3) | Alta | Confirmado |
| RNF-03 | Usabilidad | La interfaz debe ser sencilla y adecuada para usuarios con uso limitado de tecnología (cajera); la venta debe resolverse en pocos pasos | Base (2.1, 2.2) | Alta | Confirmado |
| RNF-04 | Usabilidad | Los usuarios deben poder aprender el uso básico con una capacitación breve | Propuesta | Media | A confirmar |
| RNF-05 | Disponibilidad | El sistema se aloja en la nube y se asume conectividad permanente en el local | Base (2.3) | Alta | Confirmado (contingencia: PR-29) |
| RNF-06 | Seguridad | El acceso requiere autenticación y las funciones se restringen por rol | Base (2.2) | Alta | Confirmado |
| RNF-07 | Seguridad | Las contraseñas no deben almacenarse en texto plano | Propuesta | Alta | Propuesta |
| RNF-08 | Seguridad | Los datos de clientes y saldos deben protegerse de accesos no autorizados | Propuesta | Alta | Propuesta |
| RNF-09 | Integridad | Una caja cerrada no debe poder modificarse; los movimientos deben registrar fecha y usuario | Base (CU-03) y propuesta | Alta | Confirmado en el bloqueo; auditoría: propuesta |
| RNF-10 | Integridad | Las operaciones que afectan varias tablas (venta, ingreso de mercadería, pagos) deben completarse enteras o no aplicarse | Propuesta | Alta | Propuesta |
| RNF-11 | Respaldo | Debe haber copias de seguridad periódicas de la base de datos | Propuesta | Alta | A confirmar (frecuencia) |
| RNF-12 | Rendimiento | Las operaciones de mostrador (buscar producto, registrar venta) deben responder de forma fluida; los reportes en un tiempo razonable | Propuesta | Media | A definir (umbral) |
| RNF-13 | Mantenibilidad | El sistema debe ser mantenible por una sola persona: stack simple, código documentado y con pruebas | Base (alcance académico) | Alta | Confirmado |
| RNF-14 | Compatibilidad | El sistema no se integra con Kendra ni con las balanzas | Base (1.2, 2.3) | Alta | Confirmado |
| RNF-15 | Localización | La interfaz y los reportes estarán en español, con montos en pesos argentinos | Propuesta | Media | A confirmar |
| RNF-16 | Datos | El repositorio y los entornos de desarrollo no deben contener datos reales del negocio ni credenciales | Decisión del proyecto | Alta | Confirmado |

## 4. Trazabilidad requisitos y casos de uso

| Caso de uso | Requisitos relacionados |
|---|---|
| CU-01 Registrar venta | RF-06, RF-11 a RF-20, RF-27 |
| CU-02 Abrir caja por turno | RF-04, RF-05, RF-10 |
| CU-03 Cerrar caja por turno | RF-06, RF-07, RF-08, RF-09 |
| CU-04 Registrar pago de cliente | RF-06, RF-36, RF-37, RF-38 |
| CU-05 Registrar ingreso de mercadería | RF-22, RF-23, RF-24, RF-30 |
| CU-06 Consultar stock | RF-25, RF-26, RF-28 |
| CU-07 Registrar pago a proveedor | RF-06, RF-31, RF-32, RF-33 |
| CU-08 Gestionar cuentas corrientes | RF-39, RF-40, RF-41 |
| CU-09 Generar reportes | RF-42 a RF-46 |
| CU-10 Iniciar sesión | RF-01, RF-02 |
| CU-11 Gestionar productos | RF-21, RF-17, RF-24 |
| CU-12 Gestionar clientes | RF-35 |
| CU-13 Gestionar proveedores | RF-29 |
| CU-14 Gestionar usuarios | RF-03 |
| Sin caso de uso todavía | RF-34 (pedidos a proveedor), RF-47 (datos históricos) |

## 5. Resumen de requisitos a confirmar

Los requisitos "A confirmar" dependen de las brechas de [01-relevamiento.md](01-relevamiento.md). Los de mayor impacto son:

| Requisito | Brecha | Qué se necesita saber |
|---|---|---|
| RF-18, RF-40, RF-41 | PR-12, PR-13 | Límites de crédito y plazo de vencimiento |
| RF-33, RF-34 | PR-17, PR-19 | Cómo se paga a proveedores y si los pedidos se gestionan en el sistema |
| RF-03, RF-45 | PR-25 | Quién es el Administrador y qué ven los dueños |
| RF-46 | PR-27 | Reportes automáticos o a pedido |

## 6. Mantenimiento

Al cambiar o confirmar un requisito, actualizar su fila (estado y origen), la trazabilidad de la sección 4 y los documentos afectados: casos de uso (04), modelo de datos (05) y pruebas (08).
