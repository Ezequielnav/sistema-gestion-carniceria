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
| DEC-09 | Los cambios al repositorio entran por rama y Pull Request; `main` está protegida. Se commitea en local y se publica un único PR cuando el conjunto está completo | Evitar subir cambios a cada rato | Vigente | — |
| DEC-10 | La documentación y el diseño se trabajan en el Proyecto de Claude; el código se desarrolla con Claude Code sobre el repositorio. Codex se suma más adelante | Claude Code es la herramienta que hoy usa el alumno | Vigente | 06 |
| DEC-11 | Cuando se sume Codex: pasar el contenido de `CLAUDE.md` a `AGENTS.md`, dejar en `CLAUDE.md` solo `@AGENTS.md` y configurar sus permisos | Una sola fuente de instrucciones para ambos agentes | Diferida | 06 |
| DEC-12 | Los plugins de terceros de Claude Code (karpathy y agent-skills) se configuran en `.claude/settings.local.json`, no en la configuración compartida del repositorio | Evitar que cargue código de terceros sin versión fija; el repositorio es público por ahora | Vigente | `CLAUDE.md`, `.claude/settings.json` |
| DEC-13 | El repositorio pasa a privado más adelante. Al hacerlo, verificar que la protección de `main` siga aplicándose (en el plan gratuito de GitHub puede no aplicarse a repositorios privados) | Posible pérdida de la protección de rama | Diferida (el alumno decide cuándo) | — |
| DEC-14 | `.mcp.json` (servidor de Playwright, sin secretos) queda fuera de los commits actuales; se versiona después, con versión fija en lugar de `@latest` | No es necesario para la documentación | Diferida | — |
| DEC-15 | Los riesgos de alcance de `02-alcance-objetivos.md` pasan de RI-xx a RA-xx, porque RI-xx ya identifica las reglas de integridad del modelo de datos | Evitar IDs duplicados | Vigente | 02 |
| DEC-16 | No hay fecha de entrega fija ni horas semanales fijas (PA-01, PA-06). El alumno decide cuándo presenta un avance al profesor y el trabajo se hace por sesiones. La planificación usa orden de hitos, tamaño relativo y puntos de entrega, sin semanas ni fechas | Respuesta del alumno | Vigente (si la cátedra impone una fecha, se reemplaza) | 01, 02, 07 |

## 3. Decisiones técnicas (detalle en [06-arquitectura.md](06-arquitectura.md))

| ID | Tema | Decisión | Estado |
|---|---|---|---|
| D-01 | Estilo | Arquitectura por capas, en un solo proyecto | Vigente |
| D-02 | Lenguaje y framework | Python con Django | Vigente |
| D-03 | Interfaz | Plantillas HTML, Tailwind CSS y JavaScript propio | Vigente |
| D-04 | Base de datos | PostgreSQL | Vigente |
| D-05 | Claves primarias | Enteros de 64 bits autoincrementales | Vigente |
| D-06 | Autenticación | Sesiones de Django; JWT solo si más adelante hace falta una API o app móvil | Vigente |
| D-07 | Despliegue | Diferido; por ahora todo corre en local | Diferida |
| D-08 | Copias de seguridad | Diferidas hasta tener producción | Diferida |
| D-09 | Pruebas | `pytest`, base de prueba, GitHub Actions al tener las primeras pruebas (ver [08-pruebas.md](08-pruebas.md)) | Vigente |
| D-10 | Reportes PDF y Excel | Diferidos hasta CU-09 | Diferida |
| D-11 | Impresión de ticket | Diferida; primero impresión desde el navegador | Diferida |
| D-12 | Base local | PostgreSQL instalado en la computadora; Docker diferido | Vigente |
| D-13 | Tailwind | Herramienta de línea de comandos, sin empaquetador | Vigente |
| D-14 | Credenciales locales | `.env.example` con nombres y valores de ejemplo; `.env` local ignorado y fuera del permiso de lectura de los agentes; pruebas con base y credenciales exclusivas de desarrollo | Vigente |

**Nota sobre D-14:** las reglas de denegar lectura de Claude Code no alcanzan a los procesos que lance. Se acepta porque las credenciales locales son descartables. Si más adelante hubiera secretos con valor, se agrega un entorno aislado.

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

## 5. Contradicciones del documento base (H-01 a H-14)

Se registraron al revisar el documento del alumno y están detalladas en [01-relevamiento.md](01-relevamiento.md). Hasta resolverse, cada una figura como **a confirmar** en los documentos afectados y **no** se implementa como regla.

| Estado actual | Hallazgos |
|---|---|
| Esperan respuesta del negocio | H-01, H-02, H-05, H-06, H-07, H-08, H-12, H-13 |
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
