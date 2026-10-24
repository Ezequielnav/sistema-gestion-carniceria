# 01 - Relevamiento

| Campo | Valor |
|---|---|
| Versión | 0.2 (borrador) |
| Origen | Relevamiento y entrevista reales con el responsable de la carnicería, realizados para una materia anterior (alcance menor). **No se rehace desde cero** |
| Propósito | Documentar el relevamiento ya realizado como base del proyecto y registrar las brechas que faltan validar para el alcance ampliado del Trabajo de Campo |
| Regla | No se inventa información del negocio. Todo dato faltante se lista como brecha a validar (PR-xx) |

## 1. Relevamiento base (ya realizado)

La información del documento `Trabajo_de_Campo-Sistema_de_gestion_carniceria.pdf` surge de un relevamiento real con el responsable del negocio. Es la **fuente de verdad** del proyecto y tiene prioridad sobre cualquier otro material.

**Qué cubrió el relevamiento previo**

- Contexto del negocio y del proceso actual (ver [00-contexto.md](00-contexto.md)).
- Alcance inicial: qué hará y qué no hará el sistema.
- Roles de usuario: administrador, cajera y dueños.
- Funciones principales: caja, ventas, stock no cárnico, proveedores, cuentas corrientes y reportes.
- Nueve casos de uso con prototipos, y un primer modelo de clases.

**Qué quedó corto** (porque el alcance de aquella materia era menor)

- Reglas de negocio detalladas (cierre de caja, cuentas corrientes, pagos a proveedores).
- Requisitos formales, modelo de datos completo, arquitectura, planificación y pruebas.
- Algunos casos de uso incompletos y diagramas por corregir.

La documentación nueva se construye **sobre** este relevamiento, ampliándolo y ordenándolo. Los datos nuevos solo se agregan cuando el responsable los confirma.

## 2. Cómo se cierran las brechas

No hay un nuevo ciclo de entrevistas. Lo que falta se resuelve con **una validación puntual** con el responsable del negocio (una charla corta, o consultas por mensaje), usando la lista priorizada de la sección 3. Las preguntas de prioridad media y baja pueden esperar o resolverse con supuestos de diseño que se registran en [09-decisiones.md](09-decisiones.md) y se validan cuando haya oportunidad.

**Material a solicitar** (siempre con datos de ejemplo o anonimizados; el repositorio no debe contener datos reales del negocio):

- Una planilla de Google Sheets de ejemplo de cada tipo: ingreso de mercadería, caja, ventas por turno.
- Un reporte de Kendra de ejemplo y su formato de exportación.
- Un ticket o comprobante actual.
- Listado de categorías de productos y ejemplo de plus interno.

## 3. Brechas a validar

Estas preguntas **no repiten el relevamiento**: cubren lo que el alcance ampliado necesita y el relevamiento previo no registró.

**Prioridad**

| Prioridad | Criterio | Preguntas |
|---|---|---|
| Alta | Bloquean alcance, casos de uso o modelo de datos | PR-01, PR-08, PR-12, PR-13, PR-17, PR-19, PR-25, PR-27 |
| Media | Afectan reglas y detalles del diseño | PR-02, PR-03, PR-05, PR-07, PR-09, PR-10, PR-14, PR-15, PR-18, PR-20, PR-21, PR-22, PR-26, PR-30, PR-32 |
| Baja | Se pueden resolver con un supuesto y validar después | PR-04, PR-06, PR-11, PR-16, PR-23, PR-24, PR-28, PR-29, PR-31, PR-33, PR-34, PR-35 |

Estado posible: **Pendiente**, **Respondida**, **Descartada**. La columna "Documentos afectados" indica qué actualizar al responder.

### 3.1 Ventas y carne

| ID | Pregunta | Por qué importa | Documentos afectados | Estado |
|---|---|---|---|---|
| PR-01 | ¿Cómo se registran hoy las ventas de carne y qué se quiere registrar en el sistema (total por turno, por producto, nada)? | Define si "100% de ventas en el sistema" es posible con Kendra fuera del alcance | 02, 03, 04, 05 | Pendiente |
| PR-02 | ¿Qué reportes genera Kendra y se pueden exportar (formato, frecuencia)? | Posible carga manual o importación de totales | 02, 03, 06 | Pendiente |
| PR-03 | ¿Qué productos no cárnicos se venden por peso y cuáles por unidad? | Unidad de medida en producto y stock | 05 | Pendiente |
| PR-04 | ¿Cómo es el plus interno (formato) y cuántos productos hay aproximadamente? | Catálogo y búsqueda en la venta | 03, 05 | Pendiente |

### 3.2 Caja y turnos

| ID | Pregunta | Por qué importa | Documentos afectados | Estado |
|---|---|---|---|---|
| PR-05 | ¿Se abre la caja con un monto inicial (fondo de cambio)? | Apertura de caja (CU de abrir caja) | 04, 05 | Pendiente |
| PR-06 | ¿Cuántas cajas y turnos hay, y en qué horarios? | Modelo de turno y caja | 04, 05 | Pendiente |
| PR-07 | Si al cerrar hay diferencia entre lo contado y lo registrado, ¿qué se hace y quién lo autoriza? | Cierre de caja | 03, 04 | Pendiente |
| PR-08 | ¿Qué medios de pago se aceptan exactamente (débito, crédito, QR, de qué billeteras, transferencia)? | Documento actual lista cinco medios pero no distingue débito/crédito | 03, 04, 05 | Pendiente |
| PR-09 | ¿Se necesita pagar una misma venta con más de un medio? | Una venta con un solo medio de pago o varios | 04, 05 | Pendiente |
| PR-10 | ¿Qué egresos de caja existen (gastos, retiros, pagos a proveedores)? | Tipos de egreso | 03, 04, 05 | Pendiente |
| PR-30 | Si se carga mal una venta o un movimiento de caja, ¿cómo se corrige hoy (anular, contra-asiento, editar) y quién lo autoriza? | Ningún caso de uso cubre anulaciones ni correcciones; define si el modelo necesita estados o movimientos de reversa | 03, 04, 05 | Pendiente |
| PR-31 | ¿Qué datos de contacto se guardan de clientes y proveedores (teléfono, mail, dirección, identificación fiscal)? | Define los campos de cliente y proveedor | 03, 05 | Pendiente |
| PR-32 | ¿Se hacen conteos de inventario o ajustes de stock (mermas, roturas, diferencias)? ¿Quién los autoriza? | Define si hace falta un caso de uso de ajuste de stock | 03, 04, 05 | Pendiente |
| PR-33 | ¿Quién asume el costo mensual del servicio donde se aloje el sistema (hosting, base de datos, copias de seguridad)? ¿Hay un presupuesto? | Condiciona qué opciones de alojamiento son viables | 06, 07 | Pendiente |

### 3.3 Clientes y cuentas corrientes

| ID | Pregunta | Por qué importa | Documentos afectados | Estado |
|---|---|---|---|---|
| PR-11 | ¿Aproximadamente cuántos clientes tienen cuenta corriente y cómo se registra hoy? | Volumen y migración | 05, 06 | Pendiente |
| PR-12 | ¿Existe un límite de crédito por cliente? ¿Quién lo define? | Gestionar cuentas corrientes | 03, 04, 05 | Pendiente |
| PR-13 | ¿Cuál es el plazo para considerar una deuda vencida? | Alerta de deuda vencida | 03, 04 | Pendiente |
| PR-14 | ¿Quién cobra los pagos de cuenta corriente: solo el administrador o también la cajera? | Permisos del caso de uso | 03, 04 | Pendiente |
| PR-15 | ¿Se aceptan pagos adelantados (saldo a favor)? | Documento actual prevé "anticipo" pero el modelo no lo contempla | 04, 05 | Pendiente |
| PR-16 | ¿Se aplican recargos o intereses a deudas vencidas? | Reglas de saldo | 03, 05 | Pendiente |

### 3.4 Stock, proveedores y precios

| ID | Pregunta | Por qué importa | Documentos afectados | Estado |
|---|---|---|---|---|
| PR-17 | ¿Cuántos proveedores hay y cómo se les paga (efectivo, transferencia, cheque)? | Pago a proveedores y su relación con la caja | 03, 04, 05 | Pendiente |
| PR-18 | ¿Se registran facturas o remitos de proveedores? ¿Hay pago contra entrega o a plazo? | Deuda con proveedores | 04, 05 | Pendiente |
| PR-19 | ¿Los pedidos a proveedores deben gestionarse en el sistema o quedan fuera? | El modelo actual tiene pedidos, los casos de uso no | 02, 04, 05 | Pendiente |
| PR-20 | ¿Quién define el stock mínimo y es por producto? | Alertas de stock | 03, 05 | Pendiente |
| PR-21 | ¿Qué productos tienen vencimiento y se controla por lote? | Control de vencimientos (objetivo del documento) | 03, 05 | Pendiente |
| PR-22 | ¿Quién actualiza los precios y con qué frecuencia? ¿Se guarda historial de precios? | Producto y precio | 03, 05 | Pendiente |

### 3.5 Usuarios, dispositivos y reportes

| ID | Pregunta | Por qué importa | Documentos afectados | Estado |
|---|---|---|---|---|
| PR-23 | ¿Cuántas personas usarán el sistema y desde qué dispositivos (PC de mostrador, celulares)? | Usuarios y diseño responsive | 03, 06 | Pendiente |
| PR-24 | ¿Hay impresora de tickets? ¿Qué debe contener el ticket o comprobante (sin validez fiscal)? | Emisión de comprobante | 03, 04 | Pendiente |
| PR-25 | ¿Quién es el "Administrador": el administrativo, los dueños u otra persona? ¿Qué ven los dueños? | Roles y permisos | 00, 03, 04 | Pendiente |
| PR-26 | ¿Cada persona tendrá su propio usuario y contraseña? | Seguridad y auditoría | 03, 06 | Pendiente |
| PR-27 | ¿Qué reportes se necesitan, con qué frecuencia y en qué formato? ¿Deben generarse solos al cierre o a pedido? | La meta dice "automáticos"; el caso de uso, "a pedido" | 02, 03, 04 | Pendiente |
| PR-28 | ¿Hay que cargar datos históricos desde las planillas actuales? | Migración inicial | 03, 06, 07 | Pendiente |
| PR-29 | Si falla internet en el local, ¿qué debería poder hacerse? | Internet es bueno, pero conviene definir contingencia | 03, 06 | Pendiente |
| PR-34 | ¿Después de cuánto tiempo sin uso se debe cerrar la sesión? | Seguridad en una PC compartida del mostrador; mientras tanto queda el valor por defecto de Django | 06 | Pendiente |
| PR-35 | ¿La cajera debe ver en el inicio el total vendido del día y las últimas ventas, o solo el estado de su caja? | Hoy el inicio lo muestra a todos los roles; relacionado con PR-25 | 04, 06 | Pendiente |

### 3.6 Cuestiones académicas

| ID | Pregunta | Por qué importa | Documentos afectados | Estado |
|---|---|---|---|---|
| PA-01 | ¿Cuáles son las fechas de las entregas parciales y finales? | Planificación | 07 | **Respondida (alumno):** no hay fechas fijas; el alumno decide cuándo presentar un avance al profesor. Ver DEC-16 en 09 |
| PA-02 | ¿Qué estructura y qué formato exige la cátedra para el informe? | Maquetado y secciones | informe | Pendiente |
| PA-03 | ¿Profesor y centro universitario para la portada? | Portada | informe | Pendiente |
| PA-04 | ¿La cátedra exige alguna herramienta de seguimiento (por ejemplo Jira)? | Decisión de gestión de tareas | 07, 09 | Pendiente |
| PA-05 | ¿La cátedra exige el sistema desplegado en un entorno real o alcanza con una demostración local? | Define si el alojamiento es parte de la entrega | 06, 07 | Pendiente |
| PA-06 | ¿Cuántas horas por semana se pueden dedicar al proyecto y hasta qué fecha? | Permite recalcular las duraciones de los hitos | 07 | **Respondida (alumno):** sin horas fijas; se trabaja por sesiones y se avanza lo que se pueda en cada una. Ver DEC-16 en 09 |

**Devolución del profesor (informada por el alumno):** la idea está bien encaminada; hay que mejorar la documentación y el maquetado.

## 4. Hallazgos del documento actual

Inconsistencias detectadas al revisar el documento de trabajo. Cada una indica qué se propone y qué archivo se actualiza.

| ID | Hallazgo | Propuesta | Documentos afectados |
|---|---|---|---|
| H-01 | La meta de "registrar el 100% de ventas" choca con dejar fuera Kendra y el control de cortes; el caso de registrar venta exige stock, y el stock solo cubre no cárnicos | Decidir tras PR-01 | 02, 03, 04 |
| H-02 | Consultar stock: el diagrama la conecta con Cajera y Administrador, el texto solo con Administrador | Unificar tras PR-25 | 04 |
| H-03 | Los dueños son un rol pero no aparecen en el diagrama; los reportes figuran solo para el Administrador | Agregar el actor y ajustar permisos | 03, 04 |
| H-04 | Falta un caso de uso de alta/baja/modificación de productos, clientes, proveedores y usuarios (inicio de sesión), aunque la cajera puede crear productos | Agregar casos de uso | 04 |
| H-05 | Medios de pago: se listan cinco, el caso de uso dice "efectivo, débito, etc." y la caja solo totaliza efectivo, tarjeta y transferencia | Unificar tras PR-08 | 03, 04, 05 |
| H-06 | Pago a proveedor valida "disponibilidad en caja", pero un pago por transferencia no sale de la caja del turno | Definir tras PR-17 | 04 |
| H-07 | El modelo incluye pedidos a proveedor, sin caso de uso asociado; "factura" aparece en un caso de uso sin estar modelada | Definir tras PR-18 y PR-19 | 04, 05 |
| H-08 | Anticipo, deuda vencida, límites y condiciones están en los casos de uso pero no en el modelo | Agregar entidades de cuenta corriente y movimientos | 04, 05 |
| H-09 | Modelo de clases: turno duplicado en venta y caja, un único medio de pago por venta, saldo de cliente derivable, falta plus interno, categoría y unidad de medida, rol repetido en empleado y usuario, multiplicidades mal escritas | Rediseñar el modelo | 05 |
| H-10 | Diagrama de casos de uso: flechas de extend invertidas; se escribe "include", no "includes"; "Stock actualizado" no es un caso de uso; "Crear cliente" no tiene sentido en el pago de cuenta corriente; el texto de los casos no menciona los include/extend | Rehacer el diagrama en Mermaid | 04 |
| H-11 | Prototipo de venta sin selección de cliente ni cuenta corriente | Actualizar prototipo | prototipos |
| H-12 | Casos 3.2.3, 3.2.6 y 3.2.8 incompletos (cierre de caja sin manejo de diferencias) | Completar | 04 |
| H-13 | La meta de reportes automáticos al cierre no coincide con el caso de reportes a pedido | Definir tras PR-27 | 02, 04 |
| H-14 | Falta la sección 1.3 y hay viñetas pegadas; la portada no tiene profesor ni centro | Corregir en el informe | informe |

## 5. Registro de entrevistas y consultas

Plantilla para completar en cada encuentro o consulta. Copiar una por vez.

```
### Entrevista N.º __
- Fecha:
- Participantes (rol):
- Duración:
- Preguntas tratadas (IDs):
- Respuestas y datos nuevos:
- Decisiones tomadas:
- Documentos a actualizar:
- Preguntas nuevas:
```

### Entrevista 0 - Relevamiento previo (materia anterior)
- Fecha: **(pendiente: completar)**
- Participantes: responsable de la carnicería **(pendiente: confirmar nombre y rol)**
- Resultado: base del proyecto, ver sección 1 y [00-contexto.md](00-contexto.md)
- Observación: no se dispone de notas originales de la entrevista; si existen, conviene incorporarlas.

(Las entrevistas o consultas posteriores se registran a continuación con la plantilla.)

## 6. Cómo mantener este documento

- Al responder una pregunta: cambiar el estado a **Respondida**, anotar la respuesta en el registro de entrevistas y actualizar los documentos de la columna "Documentos afectados".
- Si surgen preguntas nuevas, agregarlas con el siguiente ID libre; no reutilizar IDs.
- Las decisiones de diseño derivadas se anotan en [09-decisiones.md](09-decisiones.md).
