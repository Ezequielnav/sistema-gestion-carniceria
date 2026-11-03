# 05 - Modelo de datos

| Campo | Valor |
|---|---|
| Versión | 0.3 (borrador) |
| Base | Modelo de clases del relevamiento real, corregido y ampliado |
| Nivel | Modelo lógico. El motor de base de datos elegido (PostgreSQL) y las decisiones técnicas están en [06-arquitectura.md](06-arquitectura.md) |
| Relacionados | [03-requisitos.md](03-requisitos.md), [04-casos-de-uso.md](04-casos-de-uso.md), [01-relevamiento.md](01-relevamiento.md) |

## 1. Convenciones

- **Nombres:** entidades en singular y `snake_case` para atributos (por ejemplo `monto_total`). Toda entidad tiene `id` como clave primaria.
- **Tipos lógicos:** `int`, `string`, `text`, `decimal` (montos y cantidades), `date`, `datetime`, `boolean`, `enum`.
- **Montos:** `decimal` con dos decimales, en pesos argentinos (propuesta, a confirmar con RNF-15).
- **Marcas:** `(PDF)` = viene del modelo base. `(propuesta)` = lo agrega el análisis. `(a confirmar: PR-xx)` = depende de una brecha de [01-relevamiento.md](01-relevamiento.md).
- **Auditoría:** todas las tablas guardan `creado_en` y `actualizado_en` (no se repiten en el diccionario).
- **Enfoque iterativo:** el modelo se construye por etapas. Se mantiene lo necesario para los casos de uso actuales y se ajusta a medida que avanza el desarrollo; lo que falte o sobre se registra en [09-decisiones.md](09-decisiones.md).
- **Baja lógica:** productos, clientes, proveedores y usuarios no se borran, se marcan con `activo = false`, para conservar el historial de ventas, pagos y cuentas corrientes.

## 2. Resumen del modelo

El modelo se organiza en cuatro áreas.

| Área | Entidades |
|---|---|
| Acceso | `usuario` |
| Caja y ventas | `caja`, `cierre_caja_detalle`, `movimiento_caja`, `medio_pago`, `venta`, `detalle_venta` |
| Catálogo, stock y proveedores | `categoria`, `producto`, `ajuste_stock`, `proveedor`, `producto_proveedor`, `ingreso_mercaderia`, `detalle_ingreso`, `pago_proveedor` |
| Clientes y cuentas corrientes | `cliente`, `pago_cliente`, `movimiento_cuenta_corriente` |

Hay además tres entidades **condicionales** que solo se agregan si el negocio lo confirma o si el desarrollo lo muestra necesario: `pedido_proveedor` (PR-19), `faltante_stock` (diferida hasta responder PR-37; mientras tanto, DEC-46) y `movimiento_stock` (diferida por ahora). Se describen en la sección 6.

## 3. Diagramas

### 3.1 Vista general de relaciones

```mermaid
erDiagram
    USUARIO ||--o{ CAJA : abre
    USUARIO ||--o{ VENTA : registra
    USUARIO ||--o{ INGRESO_MERCADERIA : registra

    CAJA ||--o{ VENTA : contiene
    CAJA ||--o{ MOVIMIENTO_CAJA : registra
    CAJA ||--o{ CIERRE_CAJA_DETALLE : "se resume en"

    MEDIO_PAGO ||--o{ VENTA : "se paga con"
    MEDIO_PAGO ||--o{ MOVIMIENTO_CAJA : "se registra con"
    MEDIO_PAGO ||--o{ CIERRE_CAJA_DETALLE : "se agrupa por"
    MEDIO_PAGO ||--o{ PAGO_CLIENTE : "se paga con"
    MEDIO_PAGO ||--o{ PAGO_PROVEEDOR : "se paga con"

    VENTA ||--|{ DETALLE_VENTA : tiene
    PRODUCTO ||--o{ DETALLE_VENTA : "se vende en"
    VENTA |o--o{ MOVIMIENTO_CAJA : origina

    CATEGORIA ||--o{ PRODUCTO : clasifica
    PRODUCTO ||--o{ AJUSTE_STOCK : "se ajusta en"
    USUARIO ||--o{ AJUSTE_STOCK : registra
    PROVEEDOR ||--o{ PRODUCTO_PROVEEDOR : ofrece
    PRODUCTO ||--o{ PRODUCTO_PROVEEDOR : "es ofrecido en"
    PROVEEDOR ||--o{ INGRESO_MERCADERIA : entrega
    INGRESO_MERCADERIA ||--|{ DETALLE_INGRESO : tiene
    PRODUCTO ||--o{ DETALLE_INGRESO : ingresa
    PROVEEDOR ||--o{ PAGO_PROVEEDOR : recibe
    INGRESO_MERCADERIA |o--o{ PAGO_PROVEEDOR : "se paga con"
    PAGO_PROVEEDOR |o--o{ MOVIMIENTO_CAJA : "origina egreso"

    CLIENTE |o--o{ VENTA : compra
    CLIENTE ||--o{ PAGO_CLIENTE : realiza
    CLIENTE ||--o{ MOVIMIENTO_CUENTA_CORRIENTE : acumula
    VENTA |o--o| MOVIMIENTO_CUENTA_CORRIENTE : "genera deuda"
    PAGO_CLIENTE ||--|{ MOVIMIENTO_CUENTA_CORRIENTE : genera
    PAGO_CLIENTE |o--o{ MOVIMIENTO_CAJA : "origina ingreso"
```

### 3.2 Caja y ventas

```mermaid
classDiagram
    class usuario {
        +int id
        +string nombre_completo
        +string nombre_usuario
        +enum rol
        +boolean puede_crear_productos
        +boolean activo
    }
    class caja {
        +int id
        +date fecha
        +enum turno
        +enum estado
        +decimal monto_inicial
        +datetime abierta_en
        +datetime cerrada_en
    }
    class cierre_caja_detalle {
        +int id
        +decimal monto_sistema
        +decimal monto_contado
    }
    class movimiento_caja {
        +int id
        +datetime fecha_hora
        +enum tipo
        +decimal monto
        +enum concepto
    }
    class medio_pago {
        +int id
        +string nombre
        +boolean ingresa_a_caja
        +boolean activo
    }
    class venta {
        +int id
        +datetime fecha_hora
        +decimal monto_total
        +enum estado
        +datetime anulada_en
        +string motivo_anulacion
    }
    class detalle_venta {
        +int id
        +decimal cantidad
        +decimal precio_unitario
        +decimal subtotal
    }

    usuario "1" --> "0..*" caja : abre
    usuario "1" --> "0..*" venta : registra
    usuario "0..1" --> "0..*" venta : anula
    caja "1" --> "0..*" venta : contiene
    caja "1" --> "0..*" movimiento_caja : registra
    caja "1" --> "0..*" cierre_caja_detalle : resumen al cerrar
    medio_pago "1" --> "0..*" venta : se paga con
    medio_pago "1" --> "0..*" movimiento_caja : se registra con
    medio_pago "1" --> "0..*" cierre_caja_detalle : agrupa
    venta "1" --> "1..*" detalle_venta : contiene
    venta "0..1" --> "0..*" movimiento_caja : origina
```

### 3.3 Catálogo, stock y proveedores

```mermaid
classDiagram
    class categoria {
        +int id
        +string nombre
    }
    class producto {
        +int id
        +string nombre
        +string plus_interno
        +decimal precio_venta
        +enum unidad_medida
        +boolean controla_stock
        +decimal stock_actual
        +decimal stock_minimo
        +boolean activo
    }
    class ajuste_stock {
        +int id
        +datetime fecha_hora
        +decimal stock_anterior
        +decimal stock_nuevo
        +enum motivo
        +string observacion
    }
    class proveedor {
        +int id
        +string nombre
        +string telefono
        +string email
        +boolean activo
    }
    class producto_proveedor {
        +int id
        +decimal precio_compra
    }
    class ingreso_mercaderia {
        +int id
        +date fecha
        +decimal total
        +enum condicion_pago
    }
    class detalle_ingreso {
        +int id
        +decimal cantidad
        +decimal precio_unitario
        +date fecha_vencimiento
    }
    class pago_proveedor {
        +int id
        +datetime fecha_hora
        +decimal monto
    }

    categoria "1" --> "0..*" producto : clasifica
    producto "1" --> "0..*" ajuste_stock : se ajusta en
    producto "1" --> "0..*" producto_proveedor
    proveedor "1" --> "0..*" producto_proveedor
    proveedor "1" --> "0..*" ingreso_mercaderia : entrega
    ingreso_mercaderia "1" --> "1..*" detalle_ingreso : contiene
    producto "1" --> "0..*" detalle_ingreso : ingresa
    proveedor "1" --> "0..*" pago_proveedor : recibe
    ingreso_mercaderia "0..1" --> "0..*" pago_proveedor : se paga con
```

### 3.4 Clientes y cuentas corrientes

```mermaid
classDiagram
    class cliente {
        +int id
        +string nombre
        +string telefono
        +string direccion
        +text observaciones
        +decimal limite_credito
        +boolean activo
    }
    class pago_cliente {
        +int id
        +datetime fecha_hora
        +decimal monto
        +boolean entra_a_caja
        +enum estado
    }
    class movimiento_cuenta_corriente {
        +int id
        +datetime fecha_hora
        +enum tipo
        +decimal monto
        +date fecha_origen
        +string motivo
    }
    class venta {
        +int id
        +decimal monto_total
    }
    class medio_pago {
        +int id
        +string nombre
    }

    cliente "1" --> "0..*" pago_cliente : realiza
    cliente "1" --> "0..*" movimiento_cuenta_corriente : acumula
    cliente "0..1" --> "0..*" venta : compra
    venta "0..1" --> "0..2" movimiento_cuenta_corriente : genera deuda y su anulación
    pago_cliente "1" --> "1..*" movimiento_cuenta_corriente : genera
    medio_pago "1" --> "0..*" pago_cliente : se paga con
```

## 4. Diccionario de datos

`Req.` indica si el campo es obligatorio (S) u opcional (N). Los tipos de clave foránea se omiten: son `int` y apuntan al `id` de la entidad indicada.

### 4.1 Acceso

**usuario** (reemplaza a `empleado` y `usuario` del modelo base)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | Clave primaria |
| nombre_completo | string | S | |
| telefono | string | N | PDF: `contacto` de `empleado`, separado en dato atómico; opcional |
| email | string | N | Opcional |
| nombre_usuario | string | S | Único |
| contrasena_hash | string | S | Nunca en texto plano (RNF-07). El modelo base lo llamaba `contraseña` |
| rol | enum | S | `ADMINISTRADOR`, `CAJERA`, `DUENIO` |
| puede_crear_productos | boolean | S | Solo aplica a `CAJERA` (RN-05) |
| activo | boolean | S | Baja lógica |

**Implementación (DEC-27):** `usuario` es el modelo de usuario propio de Django (`AUTH_USER_MODEL = "usuarios.Usuario"`, hereda de `AbstractUser`), definido antes de la primera migración. Correspondencia con el diccionario:

| Diccionario | Campo en Django |
|---|---|
| `nombre_usuario` | `username` (ya es único) |
| `contrasena_hash` | `password` (hash del framework, RNF-07) |
| `activo` | `is_active` |
| `nombre_completo`, `telefono`, `rol`, `puede_crear_productos` | Campos propios; `rol` con lista fija y `CHECK` |
| `email` | `email` (ya existe en `AbstractUser`) |

`first_name` y `last_name` de `AbstractUser` se eliminan porque los reemplaza `nombre_completo`. El framework agrega además `is_staff`, `is_superuser`, `last_login`, `date_joined` y dos tablas de relación con grupos y permisos (`usuario_groups`, `usuario_user_permissions`), que quedan vacías: el panel no las muestra porque los permisos salen del rol (DEC-32).

### 4.2 Caja y ventas

**medio_pago**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| nombre | string | S | Único. Valores mencionados: efectivo, tarjeta, transferencia, QR, cuenta corriente (DEC-41) |
| ingresa_a_caja | boolean | S | `false` para cuenta corriente (DEC-41), que es el único medio con `false`; el efectivo siempre ingresa a caja (R-6, migración `caja/0010`) |
| es_efectivo | boolean | S | `true` solo en el medio en efectivo: fondo de cambio y egresos "otros" (DEC-55) |
| activo | boolean | S | |

Es una tabla y no una lista fija para poder ajustar los medios de pago sin cambiar el código.

**caja**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| fecha | date | S | |
| turno | enum | S | `MANANA`, `TARDE` (RN-02) |
| usuario_id | FK usuario | S | Quien abrió la caja |
| monto_inicial | decimal | N | Fondo de cambio en efectivo, opcional; si se deja vacío, la aplicación guarda 0 (DEC-38) |
| estado | enum | S | `ABIERTA`, `CERRADA` |
| abierta_en | datetime | S | |
| cerrada_en | datetime | N | |
| cerrada_por_usuario_id | FK usuario | N | |
| observacion_cierre | text | N | Motivo obligatorio si hay diferencia (DEC-40) |

Los totales por medio de pago (`totalEfectivo`, `totalTarjeta`, `totalTransferencia` del modelo base) ya no son columnas: se calculan desde `movimiento_caja` y se guardan al cerrar en `cierre_caja_detalle`.

**cierre_caja_detalle** (propuesta: reemplaza las columnas de totales de `caja`; `diferencia` pasa a calcularse)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| caja_id | FK caja | S | |
| medio_pago_id | FK medio_pago | S | |
| monto_sistema | decimal | S | Calculado al cerrar |
| monto_contado | decimal | S | Ingresado por la cajera (CU-03) |

Restricción: un registro por (`caja_id`, `medio_pago_id`). La diferencia (`monto_contado - monto_sistema`) no se guarda: se calcula (ver sección 5).

**movimiento_caja** (propuesta; implementa SC-02)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| caja_id | FK caja | S | Debe estar `ABIERTA` |
| fecha_hora | datetime | S | |
| tipo | enum | S | `INGRESO`, `EGRESO` |
| monto | decimal | S | Siempre positivo; el signo lo da `tipo` |
| medio_pago_id | FK medio_pago | S | |
| concepto | enum | S | `VENTA`, `PAGO_CLIENTE`, `PAGO_PROVEEDOR`, `OTRO` (gastos y retiros en efectivo, con descripción: DEC-43), `ANULACION` (egreso que revierte una venta anulada: DEC-68), `ANULACION_PAGO` (ingreso que revierte el egreso de un pago a proveedor anulado: DEC-92), `ANULACION_COBRO` (egreso que revierte el ingreso de un cobro a cliente anulado: DEC-113) |
| venta_id | FK venta | N | Si `concepto = VENTA` o `ANULACION`; a lo sumo una `ANULACION` por venta |
| pago_cliente_id | FK pago_cliente | N | Si `concepto = PAGO_CLIENTE` o `ANULACION_COBRO`; a lo sumo una `ANULACION_COBRO` por cobro |
| pago_proveedor_id | FK pago_proveedor | N | Si `concepto = PAGO_PROVEEDOR` |
| usuario_id | FK usuario | S | |
| descripcion | string | N | |

**venta**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| fecha_hora | datetime | S | El modelo base tenía `fecha` y `turno`; el turno se obtiene de `caja` |
| caja_id | FK caja | S | |
| usuario_id | FK usuario | S | Quien registró la venta (reemplaza `empleadoID`) |
| cliente_id | FK cliente | N | Obligatorio si el medio de pago es cuenta corriente (DEC-108) |
| medio_pago_id | FK medio_pago | S | Un solo medio por venta (DEC-42) |
| monto_total | decimal | S | Igual a la suma de `subtotal` de sus detalles |
| estado | enum | S | `CONFIRMADA` (por defecto) o `ANULADA`. Una venta no se edita: se anula con reversa (DEC-45, DEC-67) |
| anulada_en | datetime | N | Solo si `estado = ANULADA` |
| anulada_por_usuario_id | FK usuario | N | Quien anuló (el Administrador). Solo si `estado = ANULADA` |
| motivo_anulacion | string | N | Obligatorio si `estado = ANULADA` (DEC-66); vacío si no |

**detalle_venta**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| venta_id | FK venta | S | |
| producto_id | FK producto | S | |
| cantidad | decimal | S | Entera por `UNIDAD`, hasta 3 decimales por `KG` (DEC-48, DEC-79) |
| precio_unitario | decimal | S | Precio al momento de la venta. PDF: `precioUnitarioVenta` |
| subtotal | decimal | S | `cantidad * precio_unitario` |

### 4.3 Catálogo, stock y proveedores

**categoria** (propuesta; permite filtrar en CU-06)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| nombre | string | S | Único |

**producto**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| nombre | string | S | |
| categoria_id | FK categoria | N | |
| plus_interno | string | N | Código interno de la carnicería, único si existe; en envasados, su código de barras (DEC-37) |
| precio_venta | decimal | S | PDF: `precioUnitario` |
| unidad_medida | enum | S | `UNIDAD`, `KG`; la elige el Administrador por producto (DEC-79, supuesto) |
| controla_stock | boolean | S | `false` para los productos cárnicos (DEC-36) |
| stock_actual | decimal | S | Dato guardado: se actualiza en la misma operación que la venta, el ingreso o el cambio que hace el Administrador al crear o modificar el producto (RI-07, RI-17). Solo aplica si `controla_stock = true`; puede quedar negativo si se vende sin stock suficiente (DEC-46). PDF: `StockActual` |
| stock_minimo | decimal | N | Umbral de alerta por producto, mayor o igual a 0. Alerta si `stock_actual <= stock_minimo`; vacío, alerta si `stock_actual <= 0` (DEC-82, DEC-101, supuestos) |
| activo | boolean | S | |

El campo `fechaIngreso` del modelo base se elimina de `producto`: la fecha de cada entrada queda en `ingreso_mercaderia`.

**ajuste_stock** (registra los cambios de stock hechos a mano en CU-11; supuesto del proyecto, DEC-98)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| fecha_hora | datetime | S | |
| producto_id | FK producto | S | Con control de stock |
| usuario_id | FK usuario | S | Administrador que cambió el stock |
| stock_anterior | decimal | S | Stock del producto al guardar el ajuste (copia histórica) |
| stock_nuevo | decimal | S | Stock que cargó el Administrador, mayor o igual a 0, con el formato de DEC-79 |
| motivo | enum | S | `MODIFICACION_MANUAL` (por defecto al modificar), `CONTEO`, `VENCIMIENTO`, `ROTURA`, `OTRO` o `STOCK_INICIAL` (en el alta, DEC-99) |

La diferencia (`stock_nuevo - stock_anterior`) no se guarda (sección 5). Un ajuste no se edita ni se borra: un error se corrige volviendo a cambiar el stock, que deja otro ajuste (RI-17). No es un libro de movimientos: las ventas y los ingresos no se registran acá (`movimiento_stock` sigue diferida, sección 6).

**proveedor**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| nombre | string | S | |
| telefono | string | N | PDF: `contacto`, separado en datos atómicos; sin cambios (DEC-117) |
| email | string | N | Sin cambios (DEC-117) |
| activo | boolean | S | |

El campo `saldoPendiente` del modelo base se elimina: es un dato derivable (ver sección 5).

**producto_proveedor** (PDF)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| producto_id | FK producto | S | |
| proveedor_id | FK proveedor | S | |
| precio_compra | decimal | S | Último precio conocido; sugiere el precio en CU-05 |

Restricción: único (`producto_id`, `proveedor_id`).

**ingreso_mercaderia** (propuesta; implementa CU-05)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| fecha | date | S | |
| proveedor_id | FK proveedor | S | |
| usuario_id | FK usuario | S | |
| total | decimal | S | Suma de los detalles |
| condicion_pago | enum | S | `CONTADO` (registra el pago por el total en la misma operación) o `A_CREDITO` (deja la deuda) (DEC-81, supuesto) |
| observacion | string | N | Número de remito o de factura, texto libre (DEC-81) |
| estado | enum | S | `VIGENTE` o `ANULADO`; un ingreso no se edita, se anula (DEC-92) |
| anulado_en | datetime | N | Solo si está anulado |
| anulado_por_usuario_id | FK usuario | N | Solo si está anulado |
| motivo_anulacion | text | N | Obligatorio si está anulado |

**detalle_ingreso** (propuesta)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| ingreso_id | FK ingreso_mercaderia | S | |
| producto_id | FK producto | S | |
| cantidad | decimal | S | Entera por `UNIDAD`, hasta 3 decimales por `KG` (DEC-79); sin el tope de la venta (DEC-76) |
| precio_unitario | decimal | S | |
| fecha_vencimiento | date | N | Solo para productos con vencimiento (a confirmar: PR-21) |

**pago_proveedor** (implementa CU-07)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| fecha_hora | datetime | S | PDF: `fecha` |
| proveedor_id | FK proveedor | S | |
| ingreso_id | FK ingreso_mercaderia | N | Deuda que se paga (CU-07 permite elegir la deuda) |
| monto | decimal | S | |
| medio_pago_id | FK medio_pago | S | |
| usuario_id | FK usuario | S | |
| sale_de_caja | boolean | S | `true` si salió de la caja abierta, con su egreso; solo en efectivo (DEC-106) |
| estado | enum | S | `VIGENTE` o `ANULADO`; un pago no se edita, se anula (DEC-92). Los anulados no cuentan para el saldo |
| anulado_en | datetime | N | Solo si está anulado |
| anulado_por_usuario_id | FK usuario | N | Solo si está anulado |
| motivo_anulacion | text | N | Obligatorio si está anulado |

Los medios válidos son los activos, salvo cuenta corriente (DEC-106, supuesto). Un pago con `sale_de_caja = true`, solo en efectivo, crea además, en la misma operación, un `movimiento_caja` `EGRESO` con concepto `PAGO_PROVEEDOR` en la caja abierta del día, a nombre de quien registra el pago (DEC-80, supuesto); los demás no generan movimiento de caja. CU-07 exige `ingreso_id` aunque el campo admita nulos (DEC-81).

### 4.4 Clientes y cuentas corrientes

**cliente**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| nombre | string | S | Repetido permitido (DEC-117) |
| telefono | string | N | DEC-117 |
| direccion | string | N | DEC-117 (migración `clientes/0006`) |
| observaciones | text | N | Texto libre: notas y condiciones de crédito, sin efecto en el cálculo (DEC-112, DEC-117). Reemplaza a `condiciones`, renombrado sin perder datos (migración `clientes/0005`) |
| limite_credito | decimal | N | Se muestra "Sin límite" si está vacío y "Sin crédito habilitado" si es 0 (DEC-115). Opcional, mayor o igual a 0, lo define el Administrador; vacío = sin límite. Una venta a cuenta corriente que deja el saldo por encima del límite se rechaza (DEC-108, supuesto) |
| activo | boolean | S | |

El campo `estadoCuentaCorriente` del modelo base se elimina: el saldo se deriva de los movimientos.

**pago_cliente** (propuesta; implementa CU-04)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| fecha_hora | datetime | S | |
| cliente_id | FK cliente | S | |
| monto | decimal | S | |
| medio_pago_id | FK medio_pago | S | Cualquier medio activo salvo cuenta corriente (DEC-110) |
| usuario_id | FK usuario | S | Quien cobra: Administrador o cajera (DEC-110) |
| entra_a_caja | boolean | S | `true` si generó el `movimiento_caja` `INGRESO` `PAGO_CLIENTE` en la caja abierta del día; `false` solo si lo registró el Administrador sin caja (DEC-110, criterio de DEC-106) |
| estado | enum | S | `VIGENTE` (por defecto) o `ANULADO` (DEC-113) |
| anulado_en | datetime | N | Solo si `estado = ANULADO` |
| anulado_por_usuario_id | FK usuario | N | Quien anuló (el Administrador). Solo si `estado = ANULADO` |
| motivo_anulacion | string | N | Obligatorio si `estado = ANULADO`; vacío si no |

El monto no puede superar el saldo del cliente al cobrar (DEC-111). `entra_a_caja` y los datos de anulación se agregaron en la migración `clientes/0006`.

**movimiento_cuenta_corriente** (propuesta; libro de la cuenta corriente)

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| id | int | S | |
| cliente_id | FK cliente | S | |
| fecha_hora | datetime | S | |
| tipo | enum | S | `VENTA_FIADA` (aumenta la deuda), `PAGO` (la reduce), `ANULACION_VENTA` (reduce la deuda al anular una venta a cuenta corriente) y `ANULACION_PAGO` (la vuelve a aumentar al anular un cobro) (DEC-113), `SALDO_INICIAL` (deuda que el cliente ya tenía al empezar, aumenta la deuda) y `ANULACION_SALDO_INICIAL` (la reduce al anularlo) (DEC-119). `ANTICIPO` se quita: no hay saldo a favor (DEC-111) |
| monto | decimal | S | Siempre positivo; el efecto lo da `tipo` |
| venta_id | FK venta | N | Si `tipo = VENTA_FIADA` o `ANULACION_VENTA` |
| pago_cliente_id | FK pago_cliente | N | Si `tipo = PAGO` o `ANULACION_PAGO` |
| saldo_inicial_id | FK movimiento_cuenta_corriente | N | Solo si `tipo = ANULACION_SALDO_INICIAL`: el saldo inicial que anula; a lo sumo una anulación por saldo inicial (DEC-119) |
| fecha_origen | date | N | Obligatoria si `tipo = SALDO_INICIAL` y vacía si no; no posterior a la carga. Es la fecha que cuenta para la deuda vencida (DEC-119) |
| motivo | string | N | Obligatorio si `tipo = SALDO_INICIAL` o `ANULACION_SALDO_INICIAL` (DEC-119) |

`fecha_vencimiento` se quita: la deuda vencida se calcula al consultar con el plazo de la configuración (DEC-109). Los cambios de tipos y referencias están en las migraciones `clientes/0005` y `0006`; `clientes/0005` se detiene sin tocar nada si la base tiene anticipos o fechas de vencimiento cargadas. `motivo` admite hasta 255 caracteres.

## 5. Datos derivados (no se guardan)

| Dato | Cómo se calcula | Se usa en |
|---|---|---|
| Saldo de un cliente | Suma de `SALDO_INICIAL`, `VENTA_FIADA` y `ANULACION_PAGO` menos suma de `PAGO`, `ANULACION_VENTA` y `ANULACION_SALDO_INICIAL`; nunca menor a 0 (DEC-111, DEC-119) | CU-04, CU-08, SC-03 |
| Disponible de un cliente | `limite_credito` menos el saldo, si tiene límite (DEC-108) | SC-03 |
| Deuda vencida de un cliente | Los cobros vigentes se imputan a los cargos vigentes (ventas a cuenta corriente no anuladas y el saldo inicial vigente, este con su `fecha_origen`), del más antiguo al más nuevo; lo que queda sin cubrir de las que tienen más de `PLAZO_VENCIMIENTO_CUENTA_CORRIENTE_DIAS` (30, en `config/settings.py`) es la deuda vencida (DEC-109) | CU-08, SC-03 |
| Saldo de un ingreso | `total` menos suma de `pago_proveedor.monto` asociados | CU-07 |
| Saldo de un proveedor | Suma de los saldos de sus ingresos | CU-07 |
| Diferencia de caja por medio de pago | `monto_contado - monto_sistema` de `cierre_caja_detalle` | CU-03 |
| Total de caja por medio de pago | Suma de ingresos menos egresos de `movimiento_caja`, agrupado por `medio_pago_id` | CU-03 |
| Productos bajo el mínimo | `controla_stock = true` y `stock_actual <= stock_minimo`, o `stock_actual <= 0` si no tiene mínimo (DEC-101) | CU-06 |
| Diferencia de un ajuste | `stock_nuevo - stock_anterior` de `ajuste_stock` | CU-11 |
| Productos por vencer | `detalle_ingreso` con `fecha_vencimiento` próxima (sin descuento por lote; a confirmar: PR-21) | CU-06 |

No guardar estos valores evita que se desfasen. Si más adelante el rendimiento lo exige, se pueden guardar como datos calculados con una decisión registrada en [09-decisiones.md](09-decisiones.md).

## 6. Entidades condicionales

Solo se incorporan si el negocio lo confirma.

**pedido_proveedor** y **detalle_pedido** (a confirmar: PR-19). El modelo base tenía `PedidoProveedor` con un campo `detalle` de tipo texto. Si se gestiona, se modela con cabecera (`id`, `fecha`, `proveedor_id`, `estado`, `usuario_id`) y detalle (`pedido_id`, `producto_id`, `cantidad`), y el ingreso de mercadería podría referenciar al pedido.

**movimiento_stock** (diferida por decisión del proyecto; se reevalúa si aparecen diferencias de stock o si se confirma PR-32). Sería un libro de entradas y salidas de stock con campos tentativos: `id`, `producto_id`, `fecha_hora`, `tipo` (`INGRESO`, `VENTA`, `AJUSTE`), `cantidad` con signo, referencias al detalle de venta o de ingreso, `usuario_id` y `motivo`. Permitiría verificar que `stock_actual` coincide con lo registrado. PR-32 se cerró como supuesto con `ajuste_stock` (DEC-98), que registra solo los ajustes: el libro completo sigue diferido (DEC-24).

**faltante_stock** (diferida hasta responder PR-37; mientras tanto rige DEC-46 y el stock puede quedar negativo). Campos tentativos: `id`, `fecha_hora`, `producto_id`, `venta_id` (opcional), `cantidad_faltante`, `usuario_id`.

## 7. Normalización y buenas prácticas

### 7.1 Principios aplicados

| Principio | Cómo se aplica |
|---|---|
| Tercera forma normal (3FN) como punto de partida | Cada dato se guarda en un solo lugar; los atributos dependen de la clave de su tabla |
| Desnormalizar solo con motivo | Toda redundancia está listada en 7.3 con su justificación y su control |
| Tipos exactos para dinero | Montos y cantidades en `decimal`. El modelo base usaba `float` para montos: se cambia, porque `float` acumula errores de redondeo |
| Integridad referencial | Toda relación es una clave foránea; no se permite borrar registros referenciados (baja lógica) |
| Restricciones en la base, no solo en la aplicación | `UNIQUE`, `NOT NULL`, `CHECK` y claves foráneas protegen los datos aunque haya errores de código |
| Operaciones atómicas | Venta, ingreso, pagos y cierre de caja se ejecutan en una transacción (RNF-10) |
| Historial inmutable | Los precios se copian en los detalles; ventas y movimientos no se reescriben; una venta se anula con reversa (DEC-45) |
| Fechas | `datetime` en UTC y se muestran en la hora local; `caja.fecha` es la fecha de negocio, no se deriva del UTC |
| Nombres | Tablas en singular, `snake_case`, claves foráneas como `<entidad>_id` |
| Claves primarias | Numéricas autoincrementales de 64 bits (decisión D-05 en [06-arquitectura.md](06-arquitectura.md)) |
| Listas de valores | Las listas estables (`rol`, `turno`, `estado`, `tipo`) se implementan como enum o `CHECK`; las que el negocio puede cambiar (`medio_pago`, `categoria`) son tablas |

### 7.2 Verificación de formas normales

| Forma | Qué exige | Resultado |
|---|---|---|
| 1FN | Datos atómicos, sin listas ni grupos repetidos | Se corrigió `contacto` (podía mezclar teléfono y mail) separándolo en `telefono` y `email`. El campo `detalle` de `pedido_proveedor` del modelo base era una lista en un texto; se reemplaza por una tabla de detalle (sección 6). `condiciones` de `cliente` queda como texto libre a propósito: es una nota, no un dato consultable |
| 2FN | Sin dependencias parciales de una clave compuesta | Las tablas usan clave primaria simple (`id`). Las claves únicas compuestas (`producto_proveedor`, `cierre_caja_detalle`) tienen atributos que dependen de la clave completa |
| 3FN | Sin dependencias entre atributos que no son clave | Se eliminaron los saldos guardados (`estadoCuentaCorriente`, `saldoPendiente`), el turno repetido en `venta` y los totales fijos de `caja`. El rol deja de repetirse. Las redundancias que quedan son deliberadas (7.3) |

### 7.3 Desnormalizaciones deliberadas

| Dato redundante | Motivo | Control |
|---|---|---|
| `precio_unitario` en `detalle_venta` y `detalle_ingreso` | Es una copia histórica: el precio del producto cambia, la venta pasada no | RI-12 |
| `detalle_venta.subtotal`, `venta.monto_total`, `ingreso_mercaderia.total` | Guardan el resultado ya redondeado de la operación y facilitan reportes | RI-03; prueba automática de que el total coincide con la suma |
| `producto.stock_actual` | Conocer el stock sin sumar todas las ventas, ingresos y ajustes | Se actualiza en la misma transacción que la operación (RI-07, RI-17). Si aparecen diferencias de stock, se evalúa agregar un libro de movimientos (sección 6) |
| `stock_anterior` en `ajuste_stock` | Copia histórica del stock al cambiarlo: el stock cambia después con ventas e ingresos | RI-17 |
| `monto_sistema` en `cierre_caja_detalle` | Congela lo que decía el sistema al cerrar | Se calcula una sola vez al cerrar, y la caja queda bloqueada (RI-02) |
| `proveedor_id` en `pago_proveedor` y `cliente_id` en `movimiento_cuenta_corriente` | Permiten pagos sin deuda asociada y consultas por proveedor o cliente sin uniones | RI-14, RI-15 |
| Tres referencias opcionales en `movimiento_caja` | Evita una tabla por cada origen del movimiento | RI-13 (un `CHECK` exige exactamente una según el concepto) |

### 7.4 Restricciones sugeridas

| Entidad | Restricción |
|---|---|
| `usuario` | `UNIQUE (nombre_usuario)`; `CHECK` de `rol` |
| `medio_pago`, `categoria` | `UNIQUE (lower(nombre))`: único sin distinguir mayúsculas, para que "Efectivo" y "efectivo" no queden como dos registros (DEC-31) |
| `medio_pago` | Índice único parcial `medio_pago_un_solo_efectivo`: un solo medio con `es_efectivo = true` (DEC-55, migración `caja/0005`). Índice único parcial `medio_pago_una_sola_cuenta_corriente`: un solo medio con `ingresa_a_caja = false`, y `CHECK (ingresa_a_caja OR NOT es_efectivo)` (R-6, DEC-122, migración `caja/0010`) |
| `producto` | `UNIQUE (plus_interno)` si no es nulo; `CHECK (plus_interno IS NULL OR plus_interno <> '')` (sin código se guarda nulo, nunca texto vacío); `CHECK (precio_venta >= 0)`; `CHECK (stock_minimo >= 0)`; `CHECK` de `unidad_medida` |
| `caja` | Un índice único parcial que admite una sola caja con `estado = 'ABIERTA'` (RI-01: `caja_una_sola_abierta`, desde la migración `caja/0004` de CU-02). `UNIQUE (fecha, turno)` (`caja_unica_por_fecha_turno`) se quitó en la migración `caja/0007` (DEC-83); `CHECK (cerrada_en IS NULL OR estado = 'CERRADA')`; `CHECK` de `turno` y `estado`; `CHECK (monto_inicial >= 0)` |
| `cierre_caja_detalle` | `UNIQUE (caja_id, medio_pago_id)`; `CHECK (monto_contado >= 0)` |
| `movimiento_caja` | `CHECK (monto > 0)`; `CHECK` de coherencia entre `concepto` y referencias (RI-13); `CHECK` de `tipo` y `concepto`; `CHECK (concepto <> 'ANULACION' OR tipo = 'EGRESO')` y `UNIQUE (venta_id)` si `concepto = 'ANULACION'` (DEC-68); `CHECK (concepto <> 'ANULACION_PAGO' OR tipo = 'INGRESO')` y `UNIQUE (pago_proveedor_id, concepto)` si hay pago: un egreso y a lo sumo una reversa por pago (DEC-92); `CHECK (concepto <> 'ANULACION_COBRO' OR tipo = 'EGRESO')` y `UNIQUE (pago_cliente_id, concepto)` si hay cobro: un ingreso y a lo sumo una reversa por cobro (DEC-113, migración `caja/0010`) |
| `venta` y `detalle_venta` | `CHECK` de `estado`; `CHECK` de que `anulada_en`, `anulada_por_usuario_id` y `motivo_anulacion` estén si y solo si `estado = 'ANULADA'` (DEC-67); `CHECK (monto_total >= 0)`; `CHECK (cantidad > 0)`; `CHECK (precio_unitario >= 0)`; `CHECK (subtotal >= 0)` |
| `movimiento_cuenta_corriente` | `CHECK (monto > 0)`; `CHECK` de coherencia entre `tipo` y referencias (`VENTA_FIADA` y `ANULACION_VENTA` con `venta_id`; `PAGO` y `ANULACION_PAGO` con `pago_cliente_id`; `SALDO_INICIAL` sin referencias, con `fecha_origen` y `motivo`; `ANULACION_SALDO_INICIAL` con `saldo_inicial_id` y `motivo`); `CHECK` de `tipo`; `UNIQUE (saldo_inicial_id)` si no es nulo; `UNIQUE (venta_id, tipo)` y `UNIQUE (pago_cliente_id, tipo)` si no son nulos: una venta genera como mucho su cargo y su anulación, y un cobro, su pago y su anulación (DEC-113) |
| `pago_cliente`, `pago_proveedor` | `CHECK (monto > 0)`, coherente con `movimiento_caja` y `movimiento_cuenta_corriente`, que exigen monto positivo (más estricto que RI-16). `pago_proveedor`: `CHECK` de `estado` y de que `anulado_en`, `anulado_por_usuario_id` y `motivo_anulacion` estén si y solo si `estado = 'ANULADO'` (DEC-92). `pago_cliente`: `CHECK` de `estado` y de que `anulado_en`, `anulado_por_usuario_id` y `motivo_anulacion` estén si y solo si `estado = 'ANULADO'` (DEC-113) |
| `producto_proveedor` | `UNIQUE (producto_id, proveedor_id)`; `CHECK (precio_compra >= 0)` |
| `ingreso_mercaderia` y `detalle_ingreso` | `CHECK (total >= 0)`; `CHECK` de `condicion_pago` y de `estado`; `CHECK` de que `anulado_en`, `anulado_por_usuario_id` y `motivo_anulacion` estén si y solo si `estado = 'ANULADO'` (DEC-92, como DEC-67); `CHECK (cantidad > 0)`; `CHECK (precio_unitario >= 0)` |
| `cliente` | `CHECK (limite_credito >= 0)` |
| `ajuste_stock` | `CHECK (stock_nuevo >= 0)`; `CHECK` de `motivo` |
| Todas las claves foráneas | `ON DELETE RESTRICT` |

Con PostgreSQL, el motor elegido en [06-arquitectura.md](06-arquitectura.md), se pueden usar índices únicos parciales. Si más adelante se cambia de motor y no los admite, la regla se valida en la aplicación dentro de la transacción.

**Implementación (H1):** las claves foráneas usan `on_delete=PROTECT` de Django, que rechaza el borrado desde la aplicación. En la base, Django crea la clave foránea como `NO ACTION` diferida hasta el final de la transacción en lugar de `RESTRICT`: el efecto es el mismo (la base impide borrar un registro referenciado), pero el rechazo llega al confirmar la transacción. La prueba CP-58 fuerza el control inmediato para verificarlo. Las listas fijas (`rol`, `turno`, `estado`, `tipo`, `concepto`, `unidad_medida`, `condicion_pago`) llevan todas su `CHECK` (sección 7.1). RI-14 y RI-15 cruzan tablas y no se pueden expresar con `CHECK`: se validan en la capa de servicios.

### 7.5 Índices sugeridos

Además de los índices de las claves únicas:

| Entidad | Índice | Para qué |
|---|---|---|
| `venta` | (`caja_id`, `fecha_hora`) y (`cliente_id`) | Cierre de caja y estado de cuenta |
| `detalle_venta` | (`producto_id`) | Reportes de producto más vendido |
| `movimiento_caja` | (`caja_id`, `medio_pago_id`) | Totales por medio de pago en el cierre |
| `movimiento_cuenta_corriente` | (`cliente_id`, `fecha_hora`) | Saldo y deuda vencida |
| `pago_proveedor` | (`proveedor_id`), (`ingreso_id`) | Saldo de proveedores |
| `producto` | (`nombre`) | Búsqueda en la venta |
| `detalle_ingreso` | (`fecha_vencimiento`) cuando no es nulo | Productos por vencer |
| `ajuste_stock` | (`producto_id`, `fecha_hora`) | Ajustes de un producto |

Se ajustan con datos reales de uso; con el volumen de una carnicería, estos índices alcanzan.

## 8. Reglas de integridad

| ID | Regla | Origen |
|---|---|---|
| RI-01 | Una sola caja `ABIERTA` a la vez; puede haber varias cajas por fecha y turno, y una cerrada no se reabre (RN-01, DEC-83) | CU-02 |
| RI-02 | No se pueden agregar ni modificar ventas ni movimientos de una caja `CERRADA` (RN-03) | CU-03, RNF-09 |
| RI-03 | `venta.monto_total` es igual a la suma de los `subtotal` de sus detalles | CU-01 |
| RI-04 | Toda venta con un medio de pago que ingresa a caja genera un `movimiento_caja` de tipo `INGRESO` en la misma operación | RN-04, RNF-10 |
| RI-05 | Una venta con medio de pago cuenta corriente exige `cliente_id`, no supera el límite de crédito del cliente si lo tiene (DEC-108), no genera movimiento de caja y genera un `movimiento_cuenta_corriente` `VENTA_FIADA`; su anulación genera un `ANULACION_VENTA` en lugar del egreso de caja y se rechaza si el saldo actual es menor al total de la venta (DEC-113, DEC-114) | SC-03 |
| RI-06 | Un `pago_cliente` genera su `movimiento_cuenta_corriente` `PAGO` y no supera el saldo del cliente (sin saldo a favor, DEC-111); si `entra_a_caja`, genera además su `movimiento_caja` `PAGO_CLIENTE`. Su anulación genera un `ANULACION_PAGO` y, si entró a caja, un `ANULACION_COBRO` (DEC-113) | CU-04 |
| RI-07 | Las ventas, los ingresos, los cambios de stock del Administrador y sus anulaciones actualizan `stock_actual` solo si `producto.controla_stock = true`, dentro de la misma operación y solo con `mover_stock` (DEC-96) | CU-01, CU-05, CU-11, RNF-10 |
| RI-08 | La suma de pagos de un ingreso no puede superar su `total` | CU-07 (A2) |
| RI-09 | Un pago a proveedor que sale de la caja no puede superar el efectivo esperado de la caja abierta del día (DEC-80, DEC-106) | RN-09 |
| RI-10 | La diferencia de caja se calcula siempre como `monto_contado - monto_sistema`; no se guarda | CU-03 |
| RI-11 | Las claves foráneas no permiten borrar registros referenciados; se usa baja lógica | RNF-09 |
| RI-12 | Los precios de venta y compra se copian en el detalle al momento de la operación; cambiar el precio de un producto no altera ventas pasadas | CU-01, CU-05 |
| RI-13 | En `movimiento_caja`, según el `concepto`, exactamente una de las referencias (`venta_id`, `pago_cliente_id`, `pago_proveedor_id`) está informada y las otras son nulas; `VENTA` y `ANULACION` llevan `venta_id`; `PAGO_PROVEEDOR` y `ANULACION_PAGO`, `pago_proveedor_id`; `PAGO_CLIENTE` y `ANULACION_COBRO`, `pago_cliente_id` (DEC-113); y `OTRO` no lleva ninguna | Normalización |
| RI-14 | Si `pago_proveedor.ingreso_id` está informado, su `proveedor_id` coincide con el del ingreso | Normalización |
| RI-15 | El `cliente_id` de un `movimiento_cuenta_corriente` coincide con el de la venta o el pago que lo origina, y el de una `ANULACION_SALDO_INICIAL`, con el de su saldo inicial (DEC-119) | Normalización |
| RI-16 | Los montos y precios son mayores o iguales a cero y las cantidades de venta, ingreso y detalle son mayores a cero | RNF-10 |
| RI-17 | Cuando el Administrador cambia el stock al crear o modificar un producto, en la misma operación `stock_actual` queda igual al valor cargado (`stock_nuevo >= 0`, formato de DEC-79) y se guarda un `ajuste_stock` con el stock anterior y el nuevo; los ajustes no se editan ni se borran (DEC-98) | CU-11, RNF-10 |
| RI-18 | Un cliente tiene a lo sumo un `SALDO_INICIAL` vigente (sin su `ANULACION_SALDO_INICIAL`); lo carga y lo anula solo el Administrador, y la anulación se rechaza si el saldo actual es menor a su monto (DEC-119). Se valida en el servicio, con el cliente bloqueado: un índice no puede saber si otro movimiento anula al saldo inicial. La base asegura la parte que sí puede: una sola anulación por saldo inicial (`UNIQUE (saldo_inicial_id)`) y los datos según el tipo | CU-08 |

## 9. Cambios respecto del modelo de clases del documento base

| Cambio | Motivo |
|---|---|
| `empleado` y `usuario` se unifican en `usuario`; el rol queda una sola vez | El rol estaba repetido (H-09). Ningún caso de uso usa empleados sin acceso al sistema. Si el negocio quisiera registrar personal sin acceso, se agrega después |
| `venta` pierde `turno` y `metodoPago` (texto); gana `medio_pago_id` y `usuario_id` | El turno estaba duplicado con `caja`; el medio de pago pasa a un catálogo |
| `caja` pierde `totalEfectivo`, `totalTarjeta`, `totalTransferencia` y `diferencia`; aparecen `movimiento_caja` y `cierre_caja_detalle` | Los totales se derivan, y así se admiten QR y cuenta corriente sin cambiar la estructura (H-05) |
| `cliente.estadoCuentaCorriente` y `proveedor.saldoPendiente` se eliminan | Son datos derivables que se desfasan |
| Nuevas: `pago_cliente`, `movimiento_cuenta_corriente` | Faltaban pagos y movimientos de cuenta corriente (H-08) |
| Nuevas: `ingreso_mercaderia` y `detalle_ingreso` | Faltaba el ingreso de mercadería (H-07) |
| Nueva: `ajuste_stock` | Registro de los cambios de stock hechos a mano (CU-11, DEC-98, supuesto) |
| `producto` gana `plus_interno`, `unidad_medida`, `controla_stock`, `stock_minimo` y `categoria_id`; pierde `fechaIngreso` | Cubre stock mínimo, plus interno, unidad de medida y filtros por categoría (H-09). La fecha de ingreso pasa a `ingreso_mercaderia` |
| Vencimientos: `detalle_ingreso.fecha_vencimiento` | Cubre vencimientos sin complicar el modelo con lotes (a confirmar: PR-21) |
| `pago_proveedor` gana `ingreso_id` y `medio_pago_id` | CU-07 permite elegir la deuda y el medio de pago |
| `pedido_proveedor` pasa a entidad condicional | No tiene caso de uso asociado (H-07, PR-19) |
| Se corrigen las multiplicidades (por ejemplo, `1...*` pasa a `1..*`) | Notación UML |
| Los montos pasan de `float` a `decimal` | Evita errores de redondeo en dinero |
| `contacto` se separa en `telefono` y `email` | Datos atómicos (1FN) |
| La diferencia de caja deja de guardarse | Es derivable de dos columnas existentes |
| `cliente` gana `limite_credito` y `condiciones` (renombrado `observaciones` en H4, DEC-117) | Aparecen en el prototipo y en el texto de CU-08 |

## 10. Trazabilidad con casos de uso

| Caso de uso | Entidades principales |
|---|---|
| CU-01 Registrar venta | `venta`, `detalle_venta`, `producto`, `medio_pago`, `caja`, `movimiento_caja` |
| CU-02 Abrir caja | `caja` |
| CU-03 Cerrar caja | `caja`, `movimiento_caja`, `cierre_caja_detalle`, `medio_pago` |
| CU-04 Registrar pago de cliente | `pago_cliente`, `movimiento_cuenta_corriente`, `movimiento_caja` |
| CU-05 Registrar ingreso de mercadería | `ingreso_mercaderia`, `detalle_ingreso`, `producto`, `proveedor` |
| CU-06 Consultar stock | `producto`, `categoria`, `proveedor`, `producto_proveedor` |
| CU-07 Registrar pago a proveedor | `pago_proveedor`, `ingreso_mercaderia`, `movimiento_caja` |
| CU-08 Gestionar cuentas corrientes | `cliente`, `movimiento_cuenta_corriente` |
| CU-09 Generar reportes | `venta`, `detalle_venta`, `movimiento_caja`, `producto` |
| CU-10 Iniciar sesión, CU-14 Gestionar usuarios | `usuario` |
| CU-11 Gestionar productos | `producto`, `categoria`, `producto_proveedor`, `ajuste_stock` (DEC-98, DEC-99) |
| CU-12 Gestionar clientes | `cliente` |
| CU-13 Gestionar proveedores | `proveedor` |

## 11. Decisiones abiertas que afectan el modelo

| Brecha | Impacto en el modelo |
|---|---|
| PR-02 (reportes de Kendra) | Define si se importan totales; la venta de carne ya está decidida (DEC-36) |
| PR-12 a PR-16 | Cerradas como supuestos (DEC-108 a DEC-112): `limite_credito` opcional, sin `fecha_vencimiento` (plazo en la configuración), sin `ANTICIPO`, sin recargos y `pago_cliente.entra_a_caja`. Con DEC-113 suman `ANULACION_VENTA`, `ANULACION_PAGO`, `ANULACION_COBRO` y el estado de `pago_cliente`; con DEC-119, `SALDO_INICIAL`, `ANULACION_SALDO_INICIAL`, `fecha_origen`, `motivo` y `saldo_inicial_id`. Aplicados en las migraciones `clientes/0005` y `0006` y `caja/0010` (H4, etapa 1) |
| PR-19 | Define si existe `pedido_proveedor`. `condicion_pago` y el remito se decidieron en DEC-81 (supuesto) |
| PR-21 | Define `fecha_vencimiento`; si se pide control por lote, hay que agregar una entidad de lotes. `stock_minimo` se decidió en DEC-82 (supuesto) |
| PR-31 (datos de contacto) | Cerrada como supuesto (DEC-117): `cliente` suma `direccion` y `condiciones` pasa a `observaciones`; proveedor sin cambios; sin identificación fiscal |
| PR-11 (volumen de clientes) | Cerrada como supuesto (DEC-118): sin índices nuevos; los saldos existentes se cargan como `SALDO_INICIAL` (DEC-119) |
| PR-32 (ajustes de stock) | Cerrada como supuesto (DEC-98): se agrega `ajuste_stock`, que registra los cambios de stock de CU-11; `movimiento_stock` sigue diferida (DEC-24) |
| DEC-45 (anulaciones, ex PR-30) | `venta.estado` y los datos de la anulación (DEC-67) y el concepto `ANULACION` en `movimiento_caja` (DEC-68). Aplicado en las migraciones `caja/0006` y `ventas/0003` (H2, etapa 4) |
| DEC-39 (una caja abierta a la vez, ex PR-06), reemplazada por DEC-83 | RI-01 pasó a: una caja por (`fecha`, `turno`) y una sola caja `ABIERTA` en total (migración `caja/0004`, H2, etapa 1). Con DEC-83 queda solo una caja `ABIERTA` en total: `caja/0007` quita `UNIQUE (fecha, turno)` |
| DEC-46 (stock insuficiente) y PR-37 | Se acepta `stock_actual` negativo en productos con control de stock. Si PR-37 confirma que los faltantes se registran, se agrega `faltante_stock` (sección 6) |

## 12. Mantenimiento

Al cambiar una entidad o confirmar una brecha, actualizar este documento (diagramas, diccionario y reglas de integridad), los casos de uso en [04-casos-de-uso.md](04-casos-de-uso.md), los requisitos en [03-requisitos.md](03-requisitos.md) y las pruebas en [08-pruebas.md](08-pruebas.md). Todo cambio de estructura de datos se anota como decisión en [09-decisiones.md](09-decisiones.md).
