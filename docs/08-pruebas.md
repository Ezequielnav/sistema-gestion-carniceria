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
| Recorridos manuales | Que lo construido se puede usar, en PC y celular (RNF-02, RNF-03) | Lista de recorridos de la sección 6 | Al cerrar cada hito |
| Aceptación | Que el negocio lo considera útil | Prueba con datos ficticios frente a la cajera y el administrador | Antes de la entrega (H6) |

No se prevén pruebas de carga ni de interfaz automatizadas: no se justifican para un local con pocos usuarios simultáneos. Se reevalúa si aparece un problema de rendimiento (RNF-12, umbral a definir).

## 3. Entorno y datos de prueba

| Aspecto | Decisión |
|---|---|
| Base | PostgreSQL local, base separada de la de desarrollo; `pytest-django` la crea y la destruye en cada corrida |
| Credenciales | Exclusivas de desarrollo, definidas en el `.env` local (no se sube). Ver D-14 en [06-arquitectura.md](06-arquitectura.md) |
| Datos | Ficticios, cargados con un comando propio (H1.3) o creados dentro de cada prueba |
| Reloj | Las pruebas que dependen de fecha o turno fijan la fecha, para no depender del día en que se corren |
| Integración continua | GitHub Actions corre las pruebas en cada Pull Request cuando existan las primeras (D-09) |

## 4. Casos de prueba automáticos

Cada fila es un caso base. Al implementar el módulo se desglosan los casos (camino feliz, errores, límites) y se les asigna el ID definitivo en el código de prueba.

### 4.1 Caja (CU-02, CU-03)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-01 | Abrir caja de un turno sin caja abierta | RN-01, RF-04 | Se crea la caja en estado `ABIERTA` con fecha, turno y empleado | Confirmado |
| CP-02 | Abrir una segunda caja del mismo turno y fecha | RN-01, RI-01, RF-05 | La base y el servicio la rechazan | Confirmado |
| CP-03 | Los turnos válidos son mañana y tarde | RN-02 | Un turno distinto es rechazado | Confirmado |
| CP-04 | Cerrar caja con montos contados | RF-07, RI-10 | La diferencia es `monto_contado - monto_sistema` y no se guarda | Confirmado |
| CP-05 | Agregar una venta o un movimiento a una caja cerrada | RN-03, RI-02, RNF-09 | Se rechaza | Confirmado |
| CP-06 | Cierre con diferencia distinta de cero | RF-09 | Según lo que defina el negocio (aviso, motivo, autorización) | A confirmar (PR-07) |
| CP-07 | Abrir caja con fondo de cambio | RF-10 | Se registra el monto inicial | A confirmar (PR-05) |

### 4.2 Ventas (CU-01)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-10 | Venta con varios productos | RF-12, RI-03 | `monto_total` es la suma de los subtotales de los detalles | Confirmado |
| CP-11 | Venta en efectivo | RN-04, RI-04 | Genera un `movimiento_caja` de ingreso por el monto y el medio de pago, en la misma operación | Confirmado |
| CP-12 | Venta con producto con control de stock | RF-16, RI-07 | El `stock_actual` baja la cantidad vendida | Confirmado (no cárnicos) |
| CP-13 | Venta con producto sin control de stock | RI-07 | El stock no cambia | Confirmado |
| CP-14 | Falla a mitad de la venta (error forzado al registrar el movimiento de caja) | RNF-10 | No quedan venta, detalle, movimiento ni cambio de stock | Confirmado |
| CP-15 | Cambiar el precio de un producto después de venderlo | RI-12 | La venta anterior conserva el precio original | Confirmado |
| CP-16 | Cantidad cero o negativa, precio negativo | RI-16 | Se rechaza | Confirmado |
| CP-17 | Venta sin caja abierta | CU-01 A4, RF-15 | Se rechaza con mensaje claro | A confirmar (regla implícita en el relevamiento) |
| CP-18 | Venta a cuenta corriente con cliente | RI-05, RF-18 | Genera `VENTA_FIADA` y no genera ingreso en caja | A confirmar (PR-12, PR-13) |
| CP-19 | Venta a cuenta corriente sin cliente | RI-05 | Se rechaza | A confirmar (PR-12) |
| CP-20 | Venta de carne | RF-20 | Según el nivel de detalle que defina el negocio | A confirmar (PR-01, PR-02) |
| CP-21 | Venta con más de un medio de pago | RF-19 | Según lo que defina el negocio | A confirmar (PR-09) |

### 4.3 Stock, ingresos y proveedores (CU-05, CU-06, CU-07)

| ID | Caso | Regla | Resultado esperado | Estado |
|---|---|---|---|---|
| CP-30 | Ingreso de mercadería | RN-08, RF-23, RI-07 | El stock sube la cantidad ingresada | Confirmado |
| CP-31 | Ingreso con precio de compra | RI-12 | Se guarda el precio en el detalle del ingreso | Confirmado |
| CP-32 | Ingreso que genera deuda con el proveedor | RN-08, RF-30 | El saldo del proveedor aumenta (calculado, no guardado) | Confirmado (modalidad: PR-18) |
| CP-33 | Pago a proveedor menor o igual a la deuda | RF-31, RF-32 | El saldo baja | Confirmado |
| CP-34 | Pagos de un ingreso que superan su total | RI-08 | Se rechaza | Confirmado |
| CP-35 | Pago a proveedor con `ingreso_id` de otro proveedor | RI-14 | Se rechaza | Confirmado |
| CP-36 | Pago a proveedor desde caja sin disponibilidad | RN-09, RI-09, RF-33 | Advierte el máximo disponible | A confirmar (PR-17, H-06) |
| CP-37 | Stock por debajo del mínimo | RN-10, RF-26 | La consulta muestra la alerta | Confirmado (umbral: PR-20) |

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
| CP-50 | Inicio de sesión correcto e incorrecto | RF-01 | Entra con credenciales válidas; con inválidas, no | Confirmado |
| CP-51 | La contraseña no se guarda en texto plano | RNF-07 | En la base figura el hash | Confirmado |
| CP-52 | Usuario sin sesión accede a una pantalla | RNF-06 | Redirige al inicio de sesión | Confirmado |
| CP-53 | Dueños intentan crear o modificar datos | RN-06, RF-45 | Se rechaza; sí pueden ver reportes | Confirmado |
| CP-54 | Cajera accede a funciones de administrador | RF-02 | Se rechaza | Confirmado |
| CP-55 | Cajera sin permiso crea un producto | RN-05 | Se rechaza | Confirmado |
| CP-56 | Cajera con permiso crea un producto durante la venta | RN-05, RF-17 | Se crea | Confirmado |
| CP-57 | Baja de un producto con ventas | RI-11 | Baja lógica: el producto queda inactivo y las ventas siguen intactas | Confirmado |
| CP-58 | Intentar borrar un registro referenciado | RI-11 | La base lo impide | Confirmado |
| CP-59 | Plus interno de producto repetido (si no es nulo) y nombre de usuario repetido | `UNIQUE` de `producto` y `usuario` en la sección 7 de [05-modelo-datos.md](05-modelo-datos.md) | Se rechaza | Confirmado para `usuario`; `producto` a confirmar (PR-03, PR-22) |

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
| CP-70 | `movimiento_caja` con ninguna o más de una referencia a venta/pago | RI-13 | La base rechaza el registro |
| CP-71 | Montos negativos y cantidades menores o iguales a cero en la base | RI-16 | La base los rechaza (restricción `CHECK`, no solo validación de formulario) |
| CP-72 | Migraciones sobre base vacía | H1.2 | Se aplican sin errores |
| CP-73 | Las 17 entidades existen con sus claves y restricciones | [05-modelo-datos.md](05-modelo-datos.md) | Coincide con el modelo |

## 5. Trazabilidad de reglas a pruebas

Toda regla debe tener al menos una prueba. Si se agrega una regla, se agrega su fila.

| Regla | Casos | Regla | Casos |
|---|---|---|---|
| RN-01 | CP-01, CP-02 | RI-01 | CP-02 |
| RN-02 | CP-03 | RI-02 | CP-05 |
| RN-03 | CP-05 | RI-03 | CP-10 |
| RN-04 | CP-11, CP-40 | RI-04 | CP-11 |
| RN-05 | CP-55, CP-56 | RI-05 | CP-18, CP-19 |
| RN-06 | CP-53 | RI-06 | CP-41 |
| RN-07 | CP-41 | RI-07 | CP-12, CP-13, CP-30 |
| RN-08 | CP-30, CP-32 | RI-08 | CP-34 |
| RN-09 | CP-36 | RI-09 | CP-36 |
| RN-10 | CP-37 | RI-10 | CP-04 |
| RN-11 | CP-44 | RI-11 | CP-57, CP-58 |
| RNF-07 | CP-51 | RI-12 | CP-15, CP-31 |
| RNF-09 | CP-05 | RI-13 | CP-70 |
| RNF-10 | CP-14 | RI-14 | CP-35 |
| — | — | RI-15 | CP-42, CP-43 |
| — | — | RI-16 | CP-16, CP-71 |

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
| RM-07 | Vender a cuenta corriente, registrar un pago y ver el estado de cuenta | H4 | Administrador / Cajera |
| RM-08 | Generar un reporte, exportarlo y comparar sus totales con la caja | H5 | Administrador / Dueños |
| RM-09 | Usar el sistema desde el celular en todas las pantallas anteriores | H6 | Los tres |

## 7. Criterios de aceptación por hito

Un hito se da por terminado cuando:

1. Las pruebas automáticas de sus casos (no marcados "a confirmar") pasan.
2. Los recorridos manuales del hito se hicieron y no tienen fallas abiertas.
3. Las reglas del hito tienen su fila en la trazabilidad de la sección 5.
4. La documentación afectada de `/docs` está actualizada (ver [07-planificacion.md](07-planificacion.md)).
5. El cambio está en una rama con Pull Request, sin datos reales ni credenciales (RNF-16).

## 8. Registro de defectos

Para un proyecto individual alcanza con **GitHub Issues**, con las etiquetas `bug` y la del hito. Cada issue indica: pasos para reproducir, resultado obtenido, resultado esperado y caso de prueba (CP o RM) que lo detectó. Un defecto corregido debe sumar una prueba automática que lo cubra.

## 9. Pendientes que afectan las pruebas

| Pendiente | Efecto |
|---|---|
| PR-01, PR-02 (ventas de carne) | CP-20 no se puede definir |
| PR-07, PR-05 (diferencias y fondo de cambio) | CP-06 y CP-07 |
| PR-12, PR-13 (crédito y vencimiento) | CP-18, CP-19, CP-44 |
| PR-15 (excedente de pago) | CP-41 |
| PR-17, PR-18 (pagos y deuda a proveedores) | CP-32, CP-36 |
| PR-09 (varios medios de pago) | CP-21 |
| PR-03, PR-22 (códigos y unicidad de productos) | CP-59 |
| RNF-12 (umbral de rendimiento) | No hay prueba de rendimiento hasta definirlo |

## 10. Mantenimiento

Al confirmar una brecha, se cambia el estado del caso a `Confirmado` y se automatiza. Al cambiar un requisito (03), un caso de uso (04) o una regla del modelo (05), se revisan los casos de esta página y la trazabilidad de la sección 5.
