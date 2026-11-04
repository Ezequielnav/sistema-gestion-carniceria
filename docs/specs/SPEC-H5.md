# SPEC - H5 Reportes y usuarios (CU-09, CU-14)

**Estado:** aprobado, con S-1 a S-14 como DEC-140 a DEC-153 y R-1 a R-4 como DEC-154 (09). Al aprobarlo se cerraron S-3 (ingresos por día), S-11 (sin panel para los Administradores de CU-14) y las dependencias de la etapa 4. Etapa 1 implementada.

Fuente de verdad: `/docs`. Este spec no agrega reglas del negocio. Toma las de CU-09, CU-10 y CU-14 (04), RF-02, RF-03, RF-42 a RF-46 y RNF-09 (03), RN-06 (04), DEC-59, DEC-83 y DEC-86 (09), DEC-133 a DEC-139 (09) y los casos CP-53, CP-60 a CP-63 y CP-74 y el recorrido RM-08 (08). Las preguntas de H5 (PR-25, PR-26, PR-27 y PR-35) están cerradas como **supuestos del proyecto, no datos confirmados por el negocio** (DEC-133). Si el spec cambia después de aprobado, se anota en "Cambios después de aprobar el spec".

## 0. Módulos

| Módulo | Qué hace | Depende de |
|---|---|---|
| `roles` (CU-10) | Dueños solo en Reportes (DEC-134); inicio por rol (DEC-137); panel sin borrado de productos (DEC-138) ni de usuarios (DEC-135) | — |
| `usuarios` (CU-14) | Alta, edición de datos y rol, desactivación y reactivación, restablecer contraseña (DEC-135) | `roles` |
| `reportes` (CU-09) | Los cuatro reportes de RF-42 y la consulta de cierres por fecha (DEC-136), en pantalla | ventas, caja, clientes, catálogo (solo lectura) |
| `exportacion` (CU-09) | Excel y PDF de los cuatro reportes, con los mismos datos que la pantalla (RF-43) | `reportes` |
| `filtros-proveedores` (CU-05, CU-07) | Fechas y proveedor en los listados de ingresos y pagos (DEC-139) | — |

Orden de construcción: `roles` → `usuarios` → `reportes` → `exportacion` → `filtros-proveedores` → cierre.

## 1. Objetivo

El Administrador gestiona los usuarios del sistema, uno por persona, y consulta los reportes. Los dueños entran solo a los reportes, sin modificar nada. La cajera ve en el inicio el estado de la caja y llega directo a sus tres operaciones.

**Usuarios:** Administrador en todo; Dueños solo en Reportes (CU-09), en solo lectura; la cajera, solo su inicio nuevo (DEC-137).

### Ajustes del refactor de capas

| ID | Ajuste |
|---|---|
| R-1 | App nueva `apps/reportes`, con servicios que solo leen ventas, caja, clientes y catálogo. Ningún módulo importa `reportes`; la prueba de estructura lo verifica |
| R-2 | Cada reporte sale de consultas agrupadas en la base, no de una consulta por fila (como R-7 de H4) |
| R-3 | La pantalla y la exportación usan el mismo resultado del servicio, así los montos coinciden (CP-63) |
| R-4 | La vista de inicio elige los datos por rol: para la cajera y el dueño no calcula los totales del negocio |

### Reglas por módulo

| Módulo | Regla | Fuente |
|---|---|---|
| **roles.** Los dueños ven solo "Reportes"; cualquier otra pantalla les responde 403 | DEC-134, RN-06 | CP-53, CP-126 |
| **roles.** El inicio de la cajera muestra el estado de la caja y accesos a Registrar venta, Cobrar cuenta corriente y Cerrar caja, sin totales | DEC-137 | CP-127 |
| **roles.** El panel no borra productos ni usuarios | DEC-135, DEC-138 | CP-128 |
| **usuarios.** Solo el Administrador; un usuario por persona; sin autorregistro; nunca se borra | DEC-135, RF-03 | CP-124 |
| **usuarios.** Siempre queda al menos un Administrador activo | S-11 | CP-125 |
| **reportes.** Rango obligatorio y válido; sin datos, "Sin registros disponibles" | RF-43, RF-44, CU-09 A1 y A2 | CP-62, CP-132 |
| **reportes.** Totales iguales a los de las ventas, cobros y cajas del rango | RF-42 | CP-60, CP-61, CP-129 a CP-131 |
| **exportacion.** El archivo tiene los mismos montos que la pantalla | RF-43 | CP-63 |
| **filtros-proveedores.** Desde, hasta y proveedor, combinables y conservados al paginar | DEC-139 | CP-133 |

### Criterios de aceptación

- El Administrador da de alta una cajera con contraseña inicial, le cambia el rol, la desactiva (no puede ingresar) y la reactiva; restablece su contraseña y ella ingresa con la nueva.
- Ningún usuario se borra, ni desde `/usuarios/` ni desde el panel.
- Un dueño ingresa, ve solo "Reportes" en el menú y en el inicio, consulta los cuatro reportes y los cierres por fecha, y recibe 403 en el resto.
- La cajera ve en el inicio la caja abierta (o que no hay una) y los tres accesos, sin totales del negocio.
- Cada reporte coincide con las ventas, cobros y cajas cargados en el rango, y su Excel y su PDF tienen los mismos montos.
- Los listados de ingresos y pagos se filtran por fechas y proveedor.
- El panel no ofrece "Eliminar" en productos ni en usuarios.

**Fuera de H5:** reportes automáticos (RF-46, descartado por DEC-136); registro de auditoría aparte (DEC-135); cierre de sesión por inactividad (PR-34); cambio de contraseña por el propio usuario o recuperación por email; el tope de stock de L12; L10, L11, L13, L15 a L17 (lista L de 07); carga de datos históricos (PR-28, RF-47).

## 2. Comandos

```
Pruebas:        .venv/bin/pytest
Pruebas de JS:  node --test apps/ventas/tests/js/*.cjs
Lint:           .venv/bin/ruff check . && .venv/bin/ruff format --check .
Chequeo:        .venv/bin/python manage.py check
Migraciones:    .venv/bin/python manage.py makemigrations --check --dry-run
Estilos:        npm run estilos
Servidor:       .venv/bin/python manage.py runserver 127.0.0.1:8000
```

## 3. Estructura

```
apps/comun/views.py, menu.py      inicio por rol (R-4); "Reportes" y "Usuarios" dejan de figurar como "Pronto" (S-8)
templates/comun/inicio.html       inicio de la cajera y del dueño (S-8, S-9)
apps/catalogo/admin.py            productos sin borrado en el panel (S-14)
apps/usuarios/admin.py            usuarios sin borrado en el panel (S-14)
apps/usuarios/services.py         alta, edición, desactivación, reactivación y contraseña (S-10 a S-12)
apps/usuarios/forms.py, views.py  CU-14 en /usuarios/
apps/reportes/                    app nueva (R-1): servicios, vistas y plantillas de CU-09
apps/proveedores/views.py         filtros de ingresos y pagos (S-13)
apps/comun/tests/test_flujo_h5.py prueba integral (CP-134)
docs/                             03, 04, 05, 06, 07, 08 y 09 al día
```

**Migraciones previstas:** ninguna. `usuario` ya tiene `is_active`, `rol` y `puede_crear_productos` (DEC-27) y los reportes se calculan al consultar (DEC-21). Si al construir hace falta una, se pide antes.

**Dependencias nuevas (aprobadas para la etapa 4, S-7):** `openpyxl` para Excel y `reportlab` para PDF (no necesita bibliotecas del sistema). Se agregan al llegar a la etapa 4, con versión fija en `requirements.txt`.

## 4. Estilo de código

El mismo de H2 a H4: vistas finas con `requiere_funcion` y el control del servicio (permisos dobles), reglas en servicios, errores con `ValidationError` por campo, operaciones en `transaction.atomic()` y docstrings que citan RF, RI y DEC. Dinero con `Decimal`, también en la exportación.

## 5. Pruebas

- `pytest` con la base de prueba; nada toca la base de desarrollo.
- Cada decisión de H5 y del spec con al menos una prueba, por servicio y por pantalla (permisos con 403 para la cajera y los dueños).
- Reportes con fechas fijas, ventas anuladas, ventas a cuenta corriente, cobros con caja y sin ella y varias cajas en la misma fecha y turno (DEC-83).
- Exportación: se abre el archivo generado y se comparan sus montos con los de la pantalla.
- Prueba de estructura ampliada (R-1).
- CP nuevos propuestos: **CP-124** (gestión de usuarios), **CP-125** (último Administrador activo), **CP-126** (dueños solo en Reportes), **CP-127** (inicio de la cajera), **CP-128** (panel sin borrado de productos ni usuarios), **CP-129** (producto más vendido), **CP-130** (ingresos por día), **CP-131** (consulta de cierres por fecha), **CP-132** (rango inválido, CU-09 A2), **CP-133** (filtros de ingresos y pagos) y **CP-134** (prueba integral de H5). Se agregan a 08 al implementar cada etapa; CP-60 a CP-63 ya existen.
- Recorrido manual con Playwright en localhost con datos de ejemplo: RM-08 (reportes y exportación) y un RM nuevo de usuarios e inicio por rol.

## 6. Límites

- **Siempre:** trabajar en la rama `h5`; correr pruebas, lint, `check` y verificación de migraciones antes de commitear; actualizar `/docs` en el mismo cambio; dinero con `DecimalField` y `Decimal`; marcar las DEC de H5 como supuestos del proyecto.
- **Preguntar antes:** cada migración; cualquier dependencia distinta de `openpyxl` y `reportlab`; cambiar lo que ve el Administrador en el inicio; ampliar el alcance a algo de "Fuera de H5".
- **Nunca:** leer `.env` ni datos reales; push o PR sin pedido; inventar reglas del negocio; presentar un supuesto como dato confirmado; borrar usuarios, productos u operaciones.

## 7. Etapas

| Etapa | Alcance | CU / RF / DEC | CP |
|---|---|---|---|
| 0. Decisiones y spec | PR-25, PR-26, PR-27 y PR-35 cerradas como supuestos; L14 y filtros de L12 dentro del hito; docs al día; este borrador | DEC-132 a DEC-139 | — |
| 1. Roles, inicio y panel | Dueños solo en Reportes (menú, inicio y 403); inicio de la cajera; R-4; panel sin borrado de productos ni de usuarios | CU-10; RF-02; RN-06; DEC-134, DEC-135, DEC-137, DEC-138; S-8, S-9, S-14 | CP-53, CP-74, CP-126, CP-127, CP-128 |
| 2. Usuarios | CU-14 en `/usuarios/`: listado, alta, edición, desactivación y reactivación, restablecer contraseña; menú "Usuarios" | CU-14; RF-03; RNF-07; DEC-135; S-10 a S-12 | CP-50, CP-51, CP-59, CP-124, CP-125 |
| 3. Reportes en pantalla | App `reportes` (R-1 a R-3); los cuatro reportes con rango y "Sin registros disponibles"; consulta de cierres por fecha; menú "Reportes" para el Administrador y los dueños | CU-09; RF-42, RF-44, RF-45; DEC-59, DEC-83, DEC-136; S-1 a S-6 | CP-60, CP-61, CP-62, CP-129 a CP-132 |
| 4. Exportación | Excel y PDF de los cuatro reportes con `openpyxl` y `reportlab` (aprobadas) | CU-09; RF-43; D-10; S-7 | CP-63 |
| 5. Filtros de ingresos y pagos | Desde, hasta y proveedor en `/proveedores/ingresos/` y `/proveedores/pagos/` | CU-05, CU-07; DEC-139; S-13 | CP-133 |
| 6. Cierre de H5 | Prueba integral, RM-08 y el RM nuevo, revisión, 07 y 08 al día y Pull Request | Todos los de H5 | Todos los de H5 |

## Decisiones del spec (DEC-140 a DEC-153)

| ID | Decisión | Por qué |
|---|---|---|
| S-1 | **Ventas diarias:** una fila por fecha y turno de la caja, sumando las cajas de la misma fecha y turno (DEC-83), con la cantidad de ventas y el total; subtotal por día y total del rango. Cuenta las ventas no anuladas, incluidas las de cuenta corriente | Es el mismo criterio del resumen del día y del historial (DEC-86, DEC-124); una venta a cuenta corriente es una venta aunque no entre a caja |
| S-2 | **Producto más vendido:** ranking de productos del rango por importe vendido (suma de subtotales de ventas no anuladas), con la cantidad en su unidad (DEC-48, DEC-79); incluye la carne (DEC-36); paginado de a 25 | Kilos y unidades no se pueden comparar entre sí; el importe sí |
| S-3 | **Ingresos por día:** por fecha, las ventas que no son a cuenta corriente más los cobros de cuenta corriente, sin las anuladas. Las ventas a cuenta corriente no cuentan como ingreso. Una columna separa lo que **entró a caja** de lo que quedó **fuera de caja** (los cobros registrados sin caja, DEC-110), con el total del día. No resta egresos: no es un resultado de caja | "Ingresos" es el dinero que entra al negocio; una venta a cuenta corriente es deuda, no dinero. La caja de cada turno ya tiene su resumen de cierre |
| S-4 | **Totales por medio de pago:** en el rango, por medio, las ventas no anuladas (con una fila "Cuenta corriente" para las ventas a cuenta corriente) y los cobros vigentes; total general. El total de ventas coincide con el de S-1 | CP-61: la suma por medio coincide con el total |
| S-5 | **Consulta de cierres por fecha:** listado de las cajas cerradas del rango con fecha, turno, quién cerró y la diferencia, con enlace al reporte de cierre existente (`/caja/<id>/cierre/`). Sin exportación propia: el reporte de cierre se imprime desde el navegador | DEC-59 deja la consulta por fecha para CU-09; el reporte de cierre ya existe |
| S-6 | **Rango:** desde y hasta obligatorios, por defecto el día de hoy; desde posterior a hasta se rechaza con el mensaje de CU-09 A2; hasta no puede ser posterior a hoy. Sin tope de días | El volumen de una carnicería no lo necesita (RNF-12); un tope se agrega si un reporte tarda |
| S-7 | **Exportación:** Excel (`.xlsx`, con `openpyxl`) con los montos como números con formato de pesos, y PDF (con `reportlab`) con el nombre del negocio, el reporte, el rango y la fecha de generación. El nombre del archivo lleva el reporte y el rango. Las dos dependencias quedan aprobadas para la etapa 4 | Que el Excel se pueda sumar y el PDF se pueda imprimir o mandar; `reportlab` no necesita bibliotecas del sistema |
| S-8 | **Menú e inicio de los dueños:** "Reportes" (Administrador y Dueños) y "Usuarios" (Administrador) dejan de figurar como "Pronto". El inicio del dueño muestra solo el acceso a Reportes, sin totales | DEC-134: los dueños ven únicamente Reportes; los totales están dentro de los reportes |
| S-9 | **Inicio de la cajera:** con caja abierta, su turno, fecha, quién la abrió y la hora; sin caja abierta, "No hay caja abierta" con acceso a Caja para abrirla. Los accesos a Registrar venta, Cobrar cuenta corriente y Cerrar caja se muestran siempre: cada pantalla ya avisa si falta la caja (DEC-110) | DEC-137, sin repetir en el inicio las validaciones de cada pantalla |
| S-10 | **CU-14:** `/usuarios/` con el patrón de CU-12 y CU-13: listado de activos con "Incluir desactivados" y búsqueda por usuario o nombre; alta con usuario, nombre completo, teléfono y email opcionales, rol, "Puede crear productos" (solo para la cajera, RN-05) y contraseña inicial repetida, con los validadores de contraseña de Django; edición de esos datos salvo la contraseña; desactivar con confirmación y reactivar (POST) | Mismo patrón que clientes y proveedores; la reactivación permite deshacer una desactivación sin crear otro usuario para la misma persona |
| S-11 | **Último Administrador:** el Administrador no puede desactivarse a sí mismo ni quitarse el rol, y el sistema rechaza desactivar o cambiar el rol del último Administrador activo. Los Administradores creados en CU-14 **no entran al panel** de administración (`/admin/`): se crean con `is_staff` e `is_superuser` en falso. El panel queda solo para el superusuario técnico, que se crea con `createsuperuser` y que CU-14 no desactiva ni le cambia el rol; CU-14 no da ni quita acceso al panel | Sin un Administrador activo nadie puede gestionar usuarios. El panel es una herramienta técnica (DEC-31, DEC-32): el Administrador del negocio trabaja en las pantallas propias |
| S-12 | **Restablecer contraseña:** el Administrador escribe una contraseña nueva para el usuario (no hay email); el usuario ingresa con ella. No se obliga a cambiarla al ingresar. Desactivar a un usuario con sesión abierta lo deja afuera en su próximo pedido | Lo más simple sin correo saliente; Django ya rechaza la sesión de un usuario inactivo |
| S-13 | **Filtros de ingresos y pagos:** desde, hasta y proveedor (incluye los dados de baja), combinables y conservados al paginar, como el historial de ventas (DEC-86), con la validación de rango de S-6. Se filtra por la fecha del ingreso o del pago | DEC-139 con el mismo comportamiento que ya conocen los usuarios |
| S-14 | **Panel:** productos y usuarios sin permiso de borrado (sin "Eliminar" y sin la acción de borrar varios a la vez); la baja sigue siendo lógica | DEC-138 (L14) y DEC-135 (un usuario no se borra) |
