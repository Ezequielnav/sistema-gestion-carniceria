# Manual de usuario

Sistema de gestión de Carnicería Rojano. Guía corta de las tareas de todos los días, por rol (RNF-04). Los nombres entre comillas son los botones y menús tal como aparecen en pantalla.

| Rol | Qué hace en el sistema |
|---|---|
| **Cajera** | Abre y cierra la caja, vende, cobra cuentas corrientes y registra gastos y retiros en efectivo |
| **Administrador** | Productos y stock, clientes, proveedores, ingresos de mercadería, pagos, anulaciones y correcciones, reportes, usuarios y medios de pago. No vende ni abre la caja |
| **Dueños** | Solo consultan "Reportes" |

## Para todos

- **Entrar:** escribir usuario y contraseña. Cada persona tiene su propio usuario; no se comparten.
- **Salir:** el botón de cerrar sesión, abajo del menú.
- **Menú en el celular:** el botón de las tres rayas, arriba a la izquierda.
- **Plata:** los montos van con coma para los centavos ($ 1.500,50). La carne se carga en kg con hasta 3 decimales (0,750); el resto, por unidad.
- **Nada se borra:** una operación con error se anula con un motivo y queda registrada como anulada.

## Cajera

### Abrir la caja

1. Menú "Caja".
2. Elegir el turno (Mañana o Tarde) y, si hay, el fondo de cambio en efectivo. Si se deja vacío, queda en $ 0.
3. "Abrir caja".

Solo puede haber una caja abierta. Si quedó abierta la de otro turno o la de otro día, primero hay que cerrarla: con la caja de otro día no se puede vender ni cobrar.

### Vender

1. "Registrar venta" en el inicio, o menú "Ventas".
2. Cargar los productos:
   - **Con el lector:** escanear el código; el producto entra solo. Escanearlo otra vez suma 1 en la misma línea.
   - **Buscando:** escribir parte del nombre o el plus, elegir con las flechas y Enter, o con el mouse. "Ver productos" muestra todos.
   - **Carne por kg:** al agregarla, el cursor queda en el peso. Escribir el peso y Enter para volver al buscador.
3. Elegir el medio de pago.
   - **Cuenta corriente:** aparece la búsqueda del cliente; se ven su saldo, su límite y si tiene deuda vencida. Si la venta pasa el límite, no se puede confirmar.
4. "Confirmar venta". Se abre el ticket: "Imprimir" y después "Nueva venta".

Datos útiles:
- Si falta stock de un producto, la pantalla avisa con lo que hay, pero la venta se puede hacer igual.
- Una venta tiene hasta 50 productos distintos. Si se llega a ese número, hay que confirmarla y empezar otra.
- Si se sale de la pantalla con productos cargados, la venta queda guardada en esa pestaña y vuelve al entrar. Al volver, el aviso de stock usa el stock de ese momento.
- La cajera con permiso de alta puede crear un producto que no encuentra: "Crear producto" en la búsqueda.
- Una venta confirmada no se cambia. Si tiene un error, la anula el Administrador (ver más abajo).
- "Ventas de la caja" muestra las ventas del turno y sus tickets.

### Cobrar una cuenta corriente

1. "Cobrar cuenta corriente" en el inicio o en el menú.
2. Buscar al cliente, elegirlo y ver su saldo, que es lo máximo que se puede cobrar.
3. Escribir el monto, elegir el medio de pago y "Registrar cobro".
4. Se abre el **comprobante** (no es factura), con el saldo anterior y el que queda. "Imprimir" y "Nuevo cobro".

Para reimprimir un comprobante del turno: en la pantalla de cobro, "Cobros de esta caja" y "Comprobante". Los cobros de cajas ya cerradas los reimprime el Administrador. Sin caja abierta de hoy, no se puede cobrar.

### Gastos y retiros en efectivo

En "Caja", "Gastos y retiros en efectivo": monto, en qué se usó el efectivo y "Registrar egreso". No puede salir más efectivo del que hay en la caja.

### Cerrar la caja

1. "Cerrar caja" en el inicio o en "Caja".
2. Contar y escribir lo que hay de cada medio de pago. La pantalla muestra lo que se espera, con las ventas anuladas, los cobros y los pagos a proveedores del turno.
3. Si hay diferencia, escribir el motivo (es obligatorio).
4. "Cerrar caja". Se abre el reporte de cierre para "Imprimir".

Si el Administrador corrigió en tu turno un cobro de otro día hecho con tarjeta, transferencia o QR, lo esperado de ese medio puede verse en negativo. En la lista de cobros figura como anulación, con la fecha del cobro original. Cargá lo que realmente hay de ese medio.

Una caja cerrada no se modifica nunca.

## Administrador

### Productos y stock

- Menú "Productos": buscar por nombre o plus y filtrar por categoría, proveedor o "Solo stock bajo". La marca "Stock bajo" señala los que llegaron al mínimo.
- **Alta:** "Nuevo producto". Si controla stock, se puede cargar el stock inicial.
- **Ajuste de stock:** "Editar" en el producto, cambiar "Stock" y elegir el motivo (modificación manual, conteo, vencimiento, rotura u otro). Queda registrado en la pestaña "Ajustes de stock", con quién lo hizo y el stock anterior y el nuevo.
- **Baja:** "Dar de baja" (y "Reactivar"). Las pestañas "Categorías" y "Ajustes de stock" están en la misma pantalla.

### Clientes y cuentas corrientes

- Menú "Clientes": "Nuevo cliente", "Editar", "Dar de baja" o "Reactivar".
- **Estado de cuenta:** clic en el nombre. Muestra saldo, límite, disponible, deuda vencida y los movimientos, con el saldo después de cada uno.
- **Límite y observaciones:** en el estado de cuenta, "Guardar". Vacío es sin límite; 0 es sin crédito.
- **Deuda de antes del sistema:** "Cargar saldo inicial", con monto, fecha de origen y motivo.
- **Cobrar:** "Registrar cobro" o "Cobrar" en la fila del cliente. Con caja abierta de hoy, "Entra a la caja abierta" viene marcada. Desmarcarla (por ejemplo, para una transferencia recibida fuera del turno) registra el cobro sin pasar por la caja.
- **Comprobante:** en el detalle del cobro, "Ver comprobante".

### Proveedores e ingresos de mercadería

1. Menú "Proveedores", pestaña "Ingresos de mercadería", "Nuevo ingreso".
2. Elegir el proveedor y la condición:
   - **A crédito:** queda como deuda con el proveedor.
   - **Contado:** se elige el medio de pago y se paga en el momento. En efectivo, "Sale de la caja abierta" viene marcada: sale de la caja del día.
3. Buscar cada producto, elegirlo y cargar la cantidad. El precio de compra se completa con el último pagado a ese proveedor y se puede cambiar. Si el producto no existe, "Crear producto".
4. "Confirmar ingreso". El stock sube en la misma operación.

### Pagos a proveedores

1. Pestaña "Pagos", "Registrar pago", o "Registrar pago" en el detalle de un ingreso con saldo.
2. Elegir la deuda (el ingreso), el monto (no más que el saldo) y el medio.
3. En efectivo, "Sale de la caja abierta" viene marcada y exige la caja de hoy con efectivo suficiente. Desmarcada, el pago se registra sin movimiento de caja.

### Anular y corregir

Todas las anulaciones piden un motivo y quedan registradas. Nada se borra.

| Qué | Dónde | Condición |
|---|---|---|
| Venta | Menú "Historial de ventas", "Ver", "Anular venta" | Solo mientras su caja siga abierta, aunque sea de otro día. Devuelve el stock y descuenta la plata de la caja (si fue en efectivo, tiene que alcanzar el efectivo de la caja); si fue a cuenta corriente, baja la deuda del cliente. Con la caja cerrada, ya no se puede anular |
| Cobro de cuenta corriente | Detalle del cobro, "Anular cobro" | El saldo del cliente vuelve a subir |
| Pago a proveedor | Detalle del pago, "Anular pago" | El saldo con el proveedor vuelve a subir |
| Ingreso de mercadería | Detalle del ingreso, "Anular ingreso" | Solo sin pagos vigentes: primero se anulan sus pagos. Devuelve el stock |
| Saldo inicial | Estado de cuenta, "Anular saldo inicial" | Si el saldo del cliente alcanza |

**Cobros y pagos con la caja ya cerrada:** la caja cerrada no se toca. La devolución se registra en la **caja abierta** en ese momento, que puede ser de otro día; el detalle avisa en qué caja va. Si no hay una caja abierta, primero hay que pedirle a la cajera que la abra. Si es un cobro en efectivo y en la caja abierta no alcanza el efectivo, no se puede anular todavía. Si el cobro fue con tarjeta, transferencia o QR, se anula igual, aunque en esa caja todavía no haya entrado nada de ese medio: al cerrarla, lo esperado de ese medio puede aparecer en negativo. Es correcto, porque la devolución se registró en ese turno.

Por eso, después de una corrección así, los reportes de ese día ya no cuentan el cobro, pero el cierre de esa caja lo sigue mostrando, y la devolución aparece en el cierre de la caja donde se registró.

### Reportes

Menú "Reportes". Ver la sección de Dueños: el Administrador ve lo mismo.

### Usuarios

- Menú "Usuarios", "Nuevo usuario": usuario, nombre, rol, contraseña inicial y, para la cajera, "Puede crear productos".
- **"Editar"** cambia los datos y el rol. **"Contraseña"** pone una nueva (no hay recuperación por email). **"Desactivar"** impide entrar; "Reactivar" lo vuelve a habilitar.
- No se puede desactivar el propio usuario ni dejar el sistema sin un Administrador activo. Los usuarios marcados "Técnico" no se gestionan desde acá.

### Medios de pago

Menú "Medios de pago": "Nuevo medio de pago", "Editar" y activar o desactivar. El efectivo no se desactiva.

## Dueños

Menú "Reportes". Todo es de consulta:

1. Elegir el rango de fechas ("Desde" y "Hasta") y "Ver reporte".
2. Pestañas: "Resumen" (lo más importante del período, con gráficos), "Ventas diarias", "Producto más vendido", "Ingresos por día", "Totales por medio de pago" y "Cierres de caja", donde se abre el reporte de cierre de cada caja.
3. "Exportar a Excel" o "Exportar a PDF" descargan el reporte con el mismo rango.
4. "Ventas diarias" muestra una fila por día con sus ventas y su total; si ese día hubo más de un turno, los turnos van debajo. En el celular cada reporte muestra la fecha y el total; el detalle completo se ve en la PC, en el Excel o en el PDF.

Los reportes cuentan los cobros vigentes: un cobro anulado no figura, aunque su caja ya haya cerrado.

## Si se cae internet

El sistema no funciona sin conexión.

1. Mientras no haya internet, anotar en una **planilla en papel** cada venta (productos, cantidades, total y medio de pago) y cada cobro (cliente, monto y medio).
2. Cuando vuelva la conexión, la cajera carga cada venta y cada cobro de la planilla en la caja abierta, como siempre.
3. Cada operación queda con la fecha y la hora en que se carga, no con las de la planilla. Guardar la planilla junto con el cierre de caja de ese turno.
