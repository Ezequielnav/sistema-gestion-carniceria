# 09 - Registro de decisiones y cambios

| Campo | Valor |
|---|---|
| Versión | 0.1 (borrador) |
| Para qué sirve | Dejar escrito **qué se decidió, por qué y qué quedó diferido**, para no reabrir discusiones y para saber qué documentos tocar si algo cambia |
| Relacionado | Las decisiones técnicas D-01 a D-14 se detallan en [06-arquitectura.md](06-arquitectura.md); acá se resumen junto con las decisiones de alcance, modelo y proceso |

## 1. Cómo se usa

- Cada decisión tiene un ID **DEC-xx**, que no se reutiliza. Las técnicas de la arquitectura mantienen su ID **D-xx** y se listan en la sección 3.
- **Estado:** `Vigente`, `Diferida` (se decidió no hacerlo ahora) o `Reemplazada` (indica por cuál).
- Si la cátedra o el negocio piden un cambio, se agrega una fila nueva en la sección 7 y se actualizan los documentos que indica la columna "Documentos".
- Una decisión que cambia **no se borra**: se marca `Reemplazada` y se escribe la nueva.

## 2. Decisiones de alcance y de proceso

| ID | Decisión | Motivo | Estado | Documentos |
|---|---|---|---|---|
| DEC-01 | El relevamiento ya realizado (documento base del alumno) es la fuente de verdad; no se rehace desde cero. Las brechas se cierran con preguntas puntuales (PR-xx, PA-xx) | El relevamiento se hizo para una materia anterior con un alcance menor; rehacerlo no agrega valor | Vigente | 00, 01 |
| DEC-02 | Lo que no está confirmado se marca "a confirmar" y no se implementa como regla del negocio | No inventar información del negocio | Vigente | Todos |
| DEC-03 | Las brechas de prioridad alta (PR-01, 08, 12, 13, 17, 19, 25, 27) se validan con el responsable del negocio antes de construir los módulos que dependen de ellas | Son las que cambian el modelo o los casos de uso | Vigente | 01, 03 |
| DEC-04 | Enfoque iterativo: no se agrega complejidad por adelantado; lo que falte o sobre se ajusta sobre la marcha | Un proyecto individual con plazo acotado | Vigente | Todos |
| DEC-05 | El sistema cubre caja, ventas, stock **no cárnico**, proveedores, pagos y cuentas corrientes. Quedan fuera: control de cortes de carne, facturación electrónica e integración con Kendra y balanzas | Alcance del relevamiento base | Vigente | 02, 03 |
| DEC-06 | Se agregan los casos de uso CU-10 a CU-14 (sesión, productos, clientes, proveedores, usuarios) | El relevamiento base no los incluía y sin ellos no se pueden cargar datos (H-04) | Vigente (propuesto; a confirmar con PR-25, PR-26) | 03, 04 |
| DEC-07 | Los prototipos CU-01 a CU-09 son una referencia v0: **se rediseñan** al construir la interfaz | Ya tienen observaciones (H-11) y la interfaz final se define con Tailwind | Vigente | 04, `prototipos/` |
| DEC-08 | La documentación vive en `/docs` del repositorio, en Markdown con diagramas Mermaid, y de ahí sale el informe maquetado | El repositorio es la fuente de verdad; el profesor pidió mejorar documentación y maquetado | Vigente | Todos |
| DEC-09 | Los cambios al repositorio entran por rama y Pull Request; `main` está protegida. En la etapa de documentación se commitea en local y se publica un único PR cuando el conjunto está completo; el código va con una rama y un PR por tarea | Evitar subir cambios a cada rato | Reemplazada (DEC-34) | — |
| DEC-10 | La documentación y el diseño se trabajan en el Proyecto de Claude; el código se desarrolla con Claude Code sobre el repositorio. Codex se suma más adelante | Claude Code es la herramienta que hoy usa el alumno | Vigente | 06 |
| DEC-11 | Cuando se sume Codex: pasar el contenido de `CLAUDE.md` a `AGENTS.md`, dejar en `CLAUDE.md` solo `@AGENTS.md` y configurar sus permisos | Una sola fuente de instrucciones para ambos agentes | Diferida | 06 |
| DEC-12 | Los plugins de terceros de Claude Code (karpathy y agent-skills) se configuran en `.claude/settings.local.json`, no en la configuración compartida del repositorio | Evitar que cargue código de terceros sin versión fija; el repositorio es público por ahora | Vigente | `CLAUDE.md`, `.claude/settings.json` |
| DEC-13 | El repositorio pasa a privado más adelante. Al hacerlo, verificar que la protección de `main` siga aplicándose (en el plan gratuito de GitHub puede no aplicarse a repositorios privados) | Posible pérdida de la protección de rama | Diferida (el alumno decide cuándo) | — |
| DEC-14 | `.mcp.json` (servidor de Playwright, sin secretos ni rutas personales) se versiona con versión fija (`@playwright/mcp@0.0.83`) en lugar de `@latest`. Quedó versionado en el PR #8; antes quedaba fuera de los commits | Que todo el que clone el repositorio use el mismo servidor, sin bajar versiones nuevas sin control | Vigente | — |
| DEC-15 | Los riesgos de alcance de `02-alcance-objetivos.md` pasan de RI-xx a RA-xx, porque RI-xx ya identifica las reglas de integridad del modelo de datos | Evitar IDs duplicados | Vigente | 02 |
| DEC-16 | No hay fecha de entrega fija ni horas semanales fijas (PA-01, PA-06). El alumno decide cuándo presenta un avance al profesor y el trabajo se hace por sesiones. La planificación usa orden de hitos, tamaño relativo y puntos de entrega, sin semanas ni fechas | Respuesta del alumno | Vigente (si la cátedra impone una fecha, se reemplaza) | 01, 02, 07 |
| DEC-34 | Reemplaza a DEC-09. Los cambios entran por rama y Pull Request; `main` está protegida. El código se trabaja en una rama por hito, se commitea cuando hay un avance completo y entra a `main` en un solo Pull Request por hito, en lugar de una rama y un Pull Request por tarea. De acá en adelante los Pull Request se mergean con "Squash and merge": un commit por Pull Request en `main`. El Pull Request #6 (H1) entró con merge commit y queda así | Menos ramas y Pull Request para una sola persona, y un historial de `main` con un commit por cambio | Vigente | 07, 08 |

## 3. Decisiones técnicas (detalle en [06-arquitectura.md](06-arquitectura.md))

| ID | Tema | Decisión | Estado |
|---|---|---|---|
| D-01 | Estilo | Arquitectura por capas, en un solo proyecto | Vigente |
| D-02 | Lenguaje y framework | Python 3.13 con Django 5.2 LTS | Vigente |
| D-03 | Interfaz | Plantillas HTML, Tailwind CSS y JavaScript propio | Vigente |
| D-04 | Base de datos | PostgreSQL (18 en local) | Vigente |
| D-05 | Claves primarias | Enteros de 64 bits autoincrementales | Vigente |
| D-06 | Autenticación | Sesiones de Django; JWT solo si más adelante hace falta una API o app móvil | Vigente |
| D-07 | Despliegue | Diferido; por ahora todo corre en local | Diferida |
| D-08 | Copias de seguridad | Diferidas hasta tener producción | Diferida |
| D-09 | Pruebas | `pytest`, base de prueba y GitHub Actions en cada Pull Request, activo desde H1 (ver [08-pruebas.md](08-pruebas.md)) | Vigente |
| D-10 | Reportes PDF y Excel | Diferidos hasta CU-09 | Diferida |
| D-11 | Impresión de ticket | Diferida; primero impresión desde el navegador | Diferida |
| D-12 | Base local | PostgreSQL instalado en la computadora; Docker diferido | Vigente |
| D-13 | Tailwind | Herramienta de línea de comandos, sin empaquetador | Vigente |
| D-14 | Credenciales locales | `.env.example` con nombres y valores de ejemplo; `.env` local ignorado y fuera del permiso de lectura de los agentes; pruebas con base y credenciales exclusivas de desarrollo | Vigente |

**Nota sobre D-14:** las reglas de denegar lectura de Claude Code no alcanzan a los procesos que lance. Se acepta porque las credenciales locales son descartables. Si más adelante hubiera secretos con valor, se agrega un entorno aislado.

**Cambio en D-14 (H2):** `.claude/settings.json` deja de usar la regla `Read(./.env.*)`, que también bloqueaba `.env.example`, y deniega la lectura de cada archivo con secretos por su nombre: `.env`, `.env.local`, `.env.development`, `.env.development.local`, `.env.test`, `.env.test.local`, `.env.staging`, `.env.production`, `.env.production.local`, `.env.prod`, `.env.dev`, `.env.backup`, `.env.bak` y `.env.old`. Así el agente puede leer `.env.example`, que no tiene secretos. Un archivo `.env.*` con otro nombre no queda cubierto: si aparece uno, se agrega a la lista. `.gitignore` sigue ignorando todos los `.env.*` salvo `.env.example`.

## 4. Decisiones del modelo de datos (detalle en [05-modelo-datos.md](05-modelo-datos.md))

| ID | Decisión | Motivo | Estado |
|---|---|---|---|
| DEC-20 | El modelo tiene 17 entidades y se normaliza hasta 3FN, con desnormalizaciones deliberadas: precio unitario en los detalles, totales de venta e ingreso y `stock_actual` | Conservar el precio histórico y simplificar consultas del mostrador | Vigente |
| DEC-21 | No se guardan datos derivables: saldo de clientes y proveedores, totales de caja y diferencia de caja | Evitar inconsistencias | Vigente |
| DEC-22 | Dinero con `DecimalField`; nunca `float` | Exactitud | Vigente |
| DEC-23 | Baja lógica para registros con historia; las claves foráneas impiden el borrado físico | Preservar el historial (RI-11) | Vigente |
| DEC-24 | `movimiento_stock` queda fuera del modelo por ahora; el stock se guarda solo como `stock_actual`. Se reevalúa si aparecen diferencias de stock o se confirma PR-32 | Pedido del alumno: evitar complejidad por adelantado | Diferida |
| DEC-25 | `pedido_proveedor` y `faltante_stock` son entidades condicionales: solo se agregan si el negocio lo confirma (PR-19, SC-04) | No tienen caso de uso confirmado | Diferida |
| DEC-26 | El modelo base se rediseñó (turno duplicado, un único medio de pago por venta, saldo derivable, categoría y unidad de medida, entre otros: H-09) | Corregir inconsistencias del modelo de clases original | Vigente |
| DEC-27 | La entidad `usuario` se implementa como modelo de usuario propio de Django (`AUTH_USER_MODEL = "usuarios.Usuario"`, hereda de `AbstractUser`), definido antes de la primera migración: `nombre_usuario` → `username`, `contrasena_hash` → `password`, `activo` → `is_active`; `nombre_completo`, `telefono`, `rol` y `puede_crear_productos` son campos propios y `email` ya existe. `rol` usa una lista fija con `CHECK` | Aprovechar el hash de contraseñas, las sesiones y el panel del framework (RNF-07, D-06) sin duplicar la tabla de usuarios; cambiar el modelo de usuario después de la primera migración es costoso | Vigente |
| DEC-28 | Restricciones agregadas al implementar H1, además de las sugeridas originalmente en la sección 7.4 de 05: `CHECK` en todas las listas fijas; `pago_cliente.monto` y `pago_proveedor.monto` mayores a 0; `UNIQUE (venta_id)` parcial en `movimiento_cuenta_corriente`; `producto.plus_interno` sin texto vacío; `UNIQUE (nombre)` en `medio_pago` y `categoria` | Coherencia con el diccionario de datos, el diagrama 3.1 y las demás restricciones de montos (pedido del alumno) | Vigente |
| DEC-29 | Plantilla base (H1.4) con estilo sobrio de negocio: barra lateral verde pizarra, fondo gris claro, un único acento bordó y tipografía Atkinson Hyperlegible Next (Google Fonts, con respaldo en la fuente del sistema). El menú muestra solo las funciones confirmadas (C) para cada rol en la matriz de 04; las "a confirmar" (PR-14, PR-25) se suman al confirmarse. Las funciones sin pantalla aparecen como "Pronto". Hasta CU-10 (H1.5) se ingresa con el formulario del panel (`LOGIN_URL = "admin:login"`). El panel de administración usa la misma paleta y tipografía: `static/css/admin.css` redefine las variables de color del admin de Django (modo claro y oscuro) y `templates/admin/base_site.html` muestra el nombre del negocio, sin reemplazar el resto de sus plantillas | Pedido del alumno (estilo de negocio, sobrio y profesional); legibilidad para la cajera (RNF-03); no inventar permisos | Reemplazada por DEC-30 |
| DEC-30 | Interfaz con estilo de dashboard moderno, elegido por el alumno entre tres propuestas: barra lateral blanca con íconos (Lucide, licencia ISC), tipografía Inter, grises y rojo de la paleta de Tailwind, tarjetas con el resumen del día (ventas de hoy, estado de la caja, productos activos) y últimas ventas. No se muestra "stock bajo" hasta definir el umbral (PR-20). El panel de administración usa el tema **django-unfold** (0.110.0, en `requirements.txt`) con el mismo rojo, barra lateral por área y traducción propia de sus textos en `locale/es` (`LOCALE_PATHS`), porque la versión no trae español. El panel se ajusta para verse como `/`: solo modo claro, `static/css/admin.css` (cargado con `STYLES`) con barra lateral blanca, contenido sobre gris claro, ítem activo en gris y avatar rojo, y una copia de `unfold/helpers/navigation_user.html` en `templates/` que muestra el rol (revisarla al actualizar Unfold). Se mantienen el menú por rol de DEC-29 y el ingreso transitorio por el formulario del panel hasta CU-10 | El alumno rechazó el estilo de DEC-29 y pidió un estilo "pro" | Vigente |
| DEC-31 | En el panel de administración, los registros operativos (`caja`, `cierre_caja_detalle`, `movimiento_caja`, `venta`, `detalle_venta`, `pago_cliente`, `movimiento_cuenta_corriente`, `ingreso_mercaderia`, `detalle_ingreso`, `pago_proveedor`) son de solo lectura; se crean únicamente desde su caso de uso (H2 a H4). El stock actual del producto tampoco se edita en el panel (RI-07). `medio_pago.nombre` y `categoria.nombre` son únicos sin distinguir mayúsculas. Los formularios muestran los límites de montos y cantidades junto al campo, con mensajes en español | Una prueba manual del panel cargó ventas en una caja cerrada, con fecha futura, con subtotal distinto de cantidad × precio, con un total que no coincide con sus detalles y sin movimiento de caja. Esas reglas (RI-02, RI-03, RI-04, RI-12) viven en la capa de servicios y el panel las salteaba | Vigente |
| DEC-32 | Solo el rol `ADMINISTRADOR` puede tener `is_staff` o `is_superuser` (un `CHECK` en `usuario`): la cajera y los dueños entran solo por la pantalla propia de ingreso (CU-10) y no al panel de Django. Los permisos de las pantallas salen del campo `rol` y de la tabla de funciones del menú, sin los grupos de Django | Los permisos del panel no distinguen RN-05 ni RN-06, y una sola tabla de funciones por rol evita que el menú y las pantallas se contradigan | Vigente |
| DEC-33 | Pantalla de productos (CU-11): por defecto lista solo los activos y el Administrador puede incluir los dados de baja; la reactivación queda en el panel de administración. La cajera con permiso solo da de alta y no ve el stock. El nombre repetido no se bloquea | Supuestos más simples mientras no se confirmen CU-06 para la cajera (PR-25) y la unicidad del nombre (PR-22); reactivar no figura en CU-11 | Vigente |

## 5. Contradicciones del documento base (H-01 a H-14)

Se registraron al revisar el documento del alumno y están detalladas en [01-relevamiento.md](01-relevamiento.md). Hasta resolverse, cada una figura como **a confirmar** en los documentos afectados y **no** se implementa como regla.

| Estado actual | Hallazgos |
|---|---|
| Esperan respuesta del negocio | H-01, H-02, H-05, H-06, H-07, H-08, H-13 |
| Parcialmente resueltos | H-12 (falta PR-07) |
| Resueltos en la documentación | H-03 (actor Dueños), H-04 (CU-10 a CU-14), H-09 (modelo), H-10 (diagramas en Mermaid), H-11 (prototipos marcados como v0) |
| Para el informe final | H-14 |

Si algún hallazgo se resolvió de forma distinta a la anotada, corregir esta tabla.

## 6. Pendientes abiertos que más condicionan

| Pendiente | Qué bloquea |
|---|---|
| PR-01, PR-02 | Cómo se registra la venta de carne (RF-20, RF-16, CP-20) |
| PR-08 | Medios de pago exactos |
| PR-12, PR-13 | Cuenta corriente: límites y vencimiento |
| PR-17, PR-19 | Pagos a proveedores y pedidos |
| PR-25, PR-27 | Quién es el Administrador y reportes automáticos |
| PA-05, PR-33 | Si hace falta desplegar y con qué costo |

## 7. Registro de cambios solicitados

Se completa cuando la cátedra, el profesor o el negocio piden un cambio. La columna "Documentos" indica qué archivos de `/docs` hay que actualizar para mantener todo consistente.

| Fecha | Quién lo pide | Cambio | Decisión | Documentos a actualizar |
|---|---|---|---|---|
| 2026-10 | Profesor | Mejorar la documentación y el maquetado | Se reestructuró la documentación en `/docs` (00 a 09) | Todos |
| — | — | — | — | — |

### Guía rápida: qué actualizar según el tipo de cambio

| Si cambia... | Actualizar |
|---|---|
| Una regla del negocio o una respuesta del relevamiento | 01, 03 (estado del requisito y trazabilidad), 04 (regla o flujo), 05 (si afecta datos), 08 (caso de prueba) |
| Un requisito | 03, 04 (trazabilidad), 08 |
| Un caso de uso | 04, 03 (trazabilidad), 08 |
| El modelo de datos | 05, 06 (si afecta migraciones), 08 (integridad) |
| Una tecnología o decisión de arquitectura | 06, 09 |
| El plazo o el alcance | 02, 07, 09 |
| La entrega de la cátedra (nueva sección o formato) | Estructura del informe a partir de `/docs`; 09 (registrar el pedido) |

## 8. Mantenimiento

Este documento se actualiza **en el mismo Pull Request** que cualquier decisión nueva. Si se confirma una brecha del relevamiento, se agrega la decisión que la cierra (o se anota en la sección 5 o 6).
