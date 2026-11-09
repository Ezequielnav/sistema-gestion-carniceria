# Guía de capacitación

Capacitación breve para empezar a usar el sistema (RNF-04). Se hace en local, con los **datos de ejemplo** (ficticios), nunca con datos reales. Acompaña al [manual de usuario](manual-usuario.md).

## Antes de empezar

1. Base de desarrollo limpia y datos de ejemplo cargados: `python manage.py cargar_datos_ejemplo` (README).
2. Servidor local: `python manage.py runserver`.
3. Los usuarios de ejemplo entran con la contraseña de demostración del `.env` (`DEMO_PASSWORD`), que conoce quien prepara la capacitación:

| Usuario | Nombre | Rol |
|---|---|---|
| `cajera` | Clara Cajera | Cajera, sin permiso de alta de productos |
| `cajera_alta` | Carla Cajera | Cajera, con permiso de alta de productos |
| `admin_negocio` | Andrés Administrador | Administrador del negocio |
| `duenio` | Daniel Dueño | Dueño |

No usar `admin`: es el usuario técnico del panel de administración.

Datos de ejemplo que aparecen en el recorrido:
- **Productos:** Asado (101) y Vacío (102) por kg, sin control de stock; Aceite de girasol 1,5 l (501), Sal fina 500 g (502, con stock bajo) y Gaseosa cola 2,25 l (601), por unidad.
- **Clientes:** Juan Pérez (límite $ 50.000) y María Gómez (sin límite).
- **Proveedores:** Distribuidora La Esquina.

## Orden y duración

| Bloque | A quién | Qué se muestra | Tiempo aproximado |
|---|---|---|---|
| 1 | Todos | Entrar y salir, menú (también en el celular), nada se borra | 5 min |
| 2 | Cajera | Abrir caja, vender, cobrar cuenta corriente, gastos y cierre | 30 min |
| 3 | Administrador | Productos y stock, clientes, ingresos, pagos, anular y corregir, usuarios | 40 min |
| 4 | Dueños (y Administrador) | Reportes y exportación | 10 min |
| 5 | Todos | Qué hacer si se cae internet | 5 min |

El orden sigue el día de trabajo: primero la caja y la venta, que es lo más usado, y después la gestión. Conviene que cada persona haga cada paso con su propio usuario, no que solo mire.

## Recorrido

### 1. Para todos

- Entrar con el usuario propio y salir.
- Recorrer el menú: cada rol ve solo sus funciones.
- En un celular, abrir el menú con el botón de las tres rayas.

### 2. Cajera (`cajera`)

1. **Abrir la caja:** "Caja", turno Mañana, fondo de cambio $ 10.000, "Abrir caja".
2. **Venta en efectivo:** "Registrar venta". Escribir `501` y Enter (así funciona el lector); otra vez `501` y Enter para ver que suma en la misma línea. Buscar "Asado", elegirlo con las flechas y Enter y cargar 1,250 kg. Medio Efectivo, "Confirmar venta", mirar el ticket.
3. **Aviso de stock:** en una venta nueva, cargar 5 de Sal fina (`502`). La pantalla avisa que no alcanza el stock, pero deja vender. Confirmarla con Tarjeta.
4. **Venta a cuenta corriente:** cargar Vacío, elegir Cuenta corriente y buscar a Juan Pérez. Mirar el saldo, el límite y el disponible antes de confirmar.
5. **Cobro:** "Cobrar cuenta corriente", elegir a Juan Pérez, cobrar una parte en efectivo. Ver el comprobante con el saldo anterior y el que queda, "Imprimir" y "Nuevo cobro". Reimprimirlo desde "Cobros de esta caja".
6. **Gasto:** en "Caja", registrar un egreso de $ 2.000 ("Compra de bolsas").
7. **Cierre:** "Cerrar caja". Mirar lo esperado por medio, cargar en efectivo $ 100 menos de lo esperado, escribir el motivo y cerrar. Imprimir el reporte de cierre.

Con `cajera_alta`, mostrar además "Crear producto" cuando una búsqueda no encuentra nada.

### 3. Administrador (`admin_negocio`)

Antes, la cajera abre la caja del turno Tarde con $ 10.000 de fondo, porque varias operaciones la usan, y vende 2 Gaseosas (`601`) en efectivo.

1. **Productos y stock:** filtrar "Solo stock bajo" (aparece la Sal fina). Editar la Sal fina, cambiar el stock por conteo y ver el registro en "Ajustes de stock".
2. **Ingreso de mercadería:** "Proveedores", "Ingresos de mercadería", "Nuevo ingreso". Distribuidora La Esquina, A crédito, 24 de Sal fina a $ 600. Confirmar y ver que el stock subió.
3. **Pago al proveedor:** desde el detalle del ingreso, "Registrar pago" de una parte por transferencia. Ver que baja la deuda.
4. **Clientes:** abrir el estado de cuenta de Juan Pérez: los movimientos del recorrido de la cajera, con el saldo después de cada uno. Cargar un saldo inicial a María Gómez y cobrarle una parte con "Registrar cobro". Ver el comprobante desde el detalle del cobro.
5. **Anular una venta:** "Historial de ventas", abrir la venta de las Gaseosas, "Anular venta" con un motivo, y ver que vuelve el stock. Abrir después la venta de la Sal fina, de la mañana: como su caja ya cerró, no se puede anular.
6. **Corregir con la caja cerrada:** abrir el cobro a Juan Pérez del turno de la mañana, que ya cerró. El detalle avisa que la devolución va en la caja abierta de la tarde. Anularlo con un motivo y ver:
   - que la caja de la mañana no cambió;
   - que la devolución figura en la caja de la tarde;
   - que el saldo de Juan Pérez volvió a subir.
7. **Usuarios:** crear una cajera de prueba con contraseña inicial, entrar con ella en una ventana privada del navegador, cambiarle la contraseña con "Contraseña" y desactivarla.

### 4. Dueños (`duenio`)

1. "Reportes": rango de hoy, "Resumen".
2. Recorrer "Ventas diarias", "Ingresos por día" y "Totales por medio de pago" y compararlos con lo que se hizo en la caja.
3. Explicar que el cobro anulado en el paso 3.6 ya no figura en los ingresos de su día, aunque el cierre de la mañana lo conserve.
4. "Cierres de caja": abrir el cierre de la mañana. "Exportar a Excel" y "Exportar a PDF" de un reporte.

### 5. Si se cae internet

Repasar la sección del manual: planilla en papel con ventas y cobros, y carga en la caja abierta cuando vuelve la conexión, con la hora de la carga. Practicarlo con dos ventas anotadas a mano que la cajera carga después.

## Al terminar

- Preguntar a cada persona qué le costó y anotarlo como observación del recorrido (08).
- Volver a cargar una base limpia antes del uso real. Los datos de la capacitación son ficticios y no se usan después.
