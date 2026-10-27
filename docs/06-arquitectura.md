# 06 - Arquitectura y tecnologías

| Campo | Valor |
|---|---|
| Versión | 0.2 (borrador) |
| Estado | Stack **confirmado por el alumno**; claves primarias y autenticación resueltas por recomendación (a confirmar). El despliegue queda **diferido** |
| Base | Requisitos no funcionales de [03-requisitos.md](03-requisitos.md) y modelo de [05-modelo-datos.md](05-modelo-datos.md) |
| Criterio | Se incluye ahora lo que es barato de definir y caro de cambiar después. Lo que agrega complejidad permanente y se puede sumar más adelante queda diferido |
| Alcance de esta etapa | Dejar funcionando **en local** la base de datos, el back y el front. No se preparan archivos de despliegue |

> Las versiones se eligieron al iniciar el desarrollo (H1) y se anotan en D-02 y D-04; las dependencias de Python quedan con versión fija en `requirements.txt`.

## 1. Requisitos que condicionan la arquitectura

| Requisito | Qué implica técnicamente |
|---|---|
| RNF-01, RNF-02 | Aplicación web usable en PC, celular y tablet desde Chrome |
| RNF-03 | Pantallas simples, pocos pasos en la venta |
| RNF-05 | Pensada para la nube; el despliegue se prepara más adelante |
| RNF-06, RNF-07, RNF-08 | Autenticación, permisos por rol, contraseñas protegidas |
| RNF-09, RNF-10 | Transacciones: venta, ingreso y pagos se aplican completos o no se aplican |
| RNF-13 | Mantenible por una sola persona: pocas piezas, código con pruebas |
| RNF-14, RNF-16 | Sin integración con Kendra; sin datos reales ni credenciales reales en el repositorio |
| RF-43 | Exportar reportes a PDF y Excel |

## 2. Decisiones

La columna "Reversibilidad" aplica el criterio: lo difícil de revertir se decide ahora.

| ID | Tema | Decisión | Origen | Reversibilidad |
|---|---|---|---|---|
| D-01 | Estilo de arquitectura | Arquitectura **por capas**, en un solo proyecto (monolito en capas) | Elegido por el alumno | Difícil |
| D-02 | Lenguaje y framework | Python con **Django**. Versiones: Python 3.13 y Django 5.2 LTS (`requirements.txt`) | Elegido por el alumno | Difícil |
| D-03 | Interfaz | HTML con plantillas de Django, **Tailwind CSS** y **JavaScript** propio | Elegido por el alumno | Media |
| D-04 | Base de datos | **PostgreSQL**. Versión local: 18 | Elegido por el alumno | Difícil |
| D-05 | Claves primarias | Numéricas autoincrementales de 64 bits | Recomendación (delegada por el alumno) | Difícil |
| D-06 | Autenticación | **Sesiones de Django** con permisos por rol. JWT no se usa por ahora. En H1 los permisos salen del campo `rol` del usuario y de una tabla de funciones por rol (`apps/comun/menu.py`), la misma que arma el menú; no se usan los grupos de Django (DEC-32) | Recomendación (delegada por el alumno) | Media |
| D-07 | Alojamiento y despliegue | Diferido: no se preparan archivos por ahora | Pedido del alumno | Fácil |
| D-08 | Copias de seguridad | Diferidas hasta tener producción; en local, volcado manual cuando se necesite | Consecuencia de D-07 | Fácil |
| D-09 | Pruebas | `pytest` con una base de datos de prueba; GitHub Actions (`.github/workflows/pruebas.yml`) corre ruff, el control de migraciones y las pruebas con PostgreSQL 18 en cada Pull Request y en `main` (desde H1) | Propuesta | Fácil |
| D-10 | Reportes PDF y Excel | Diferidos hasta CU-09 | Propuesta | Fácil |
| D-11 | Impresión de ticket | Diferida; primero impresión desde el navegador | Propuesta | Fácil |
| D-12 | Base de datos local | PostgreSQL instalado en la computadora; Docker queda diferido | Propuesta | Fácil |
| D-13 | Compilación de Tailwind | Con su herramienta de línea de comandos (Tailwind 4.3.3 instalado con `npm` solo para compilar: `npm run estilos`), sin empaquetador de JavaScript. Node también corre las pruebas de JavaScript puro con su ejecutor incluido (`node --test`), llamado desde `pytest`, sin dependencias de `npm` | Propuesta | Fácil |
| D-14 | Credenciales de la base local | `.env.example` solo con nombres y valores de ejemplo; el `.env` local queda fuera de GitHub y del permiso de lectura de los agentes; las pruebas usan una base de prueba con credenciales exclusivas de desarrollo | Decidida (sección 6) | Fácil |

### 2.1 Autenticación: por qué sesiones y no JWT (D-06)

| Criterio | Sesiones de Django | JWT |
|---|---|---|
| Tipo de sistema | Páginas generadas por el servidor, que es nuestro caso | Pensado para un frontend separado, una app móvil o una API pública |
| Piezas que se agregan | Ninguna, viene con el framework | Librería adicional, manejo de tokens de acceso y de renovación |
| Cierre de sesión y revocación | Inmediatos: se borra la sesión en el servidor | Más complejo: el token vale hasta que vence, salvo que se agregue una lista de revocados |
| Protección de formularios | CSRF incluido | Hay que resolverla aparte |
| Dónde se guarda en el navegador | Cookie protegida que el JavaScript no puede leer | Si se guarda donde el JavaScript puede leerlo, un fallo de seguridad en la página expone el token |
| Encaja con "una sola persona" | Muy bien | Más decisiones y más código |

**Recomendación:** sesiones. Si más adelante hace falta una API para una app móvil u otro cliente, se agrega JWT en esa parte sin cambiar lo existente, por eso la reversibilidad es media.

### 2.2 Claves primarias (D-05)

Se usan enteros de 64 bits autoincrementales, que es el valor por defecto de Django. Son simples, ocupan poco, ordenan bien los índices y facilitan la depuración. El UUID sería útil si varios sistemas generaran identificadores por separado o si los identificadores se expusieran públicamente, y no es el caso. Los permisos por rol evitan que alguien recorra registros cambiando un número en la dirección.

### 2.3 Interfaz con Tailwind, HTML y JavaScript (D-03, D-13)

- **HTML:** plantillas de Django con una plantilla base y fragmentos reutilizables (menú por rol, tablas, formularios, avisos).
- **Tailwind CSS:** diseño responsive desde el celular hacia la PC. Se compila a un único archivo de estilos con su herramienta de línea de comandos. Se verifica en la instalación si la versión elegida ofrece un ejecutable independiente que no requiere Node; si no, se usa `npm` solo para esa compilación.
- **JavaScript:** archivos propios, sin empaquetador ni librería pesada. Se usa donde la pantalla lo necesita, por ejemplo en la venta para buscar productos, sumar líneas y mostrar el total. Esas pantallas consultan unos pocos puntos internos de la misma aplicación que devuelven JSON; no son una API pública y usan la sesión y el CSRF de siempre.
- **Mostrador:** botones y campos grandes y buen contraste, pensando en uso táctil y en pantallas de PC chicas.
- **Lector de códigos de barras:** los lectores USB comunes escriben el código como si fuera un teclado, por lo que alcanza con un campo de búsqueda enfocado (RF-11). El lector carga el plus interno (DEC-37).

## 3. Arquitectura por capas

```mermaid
flowchart TB
    NAV[Navegador - Chrome en PC, celular o tablet]

    subgraph L1[Capa de presentación]
        TPL[Plantillas HTML]
        TW[Estilos Tailwind]
        JS[JavaScript]
    end

    subgraph L2[Capa de vistas]
        VIS[Vistas y formularios]
        AUT[Autenticación y permisos por rol]
    end

    subgraph L3[Capa de servicios - reglas de negocio]
        SRV[Servicios por módulo]
        TX[Transacciones]
    end

    subgraph L4[Capa de acceso a datos]
        MOD[Modelos y consultas ORM]
        MIG[Migraciones]
    end

    DB[(PostgreSQL)]

    NAV --> TPL
    TPL --- TW
    TPL --- JS
    JS --> VIS
    TPL --> VIS
    VIS --> AUT
    VIS --> SRV
    SRV --> TX
    SRV --> MOD
    MOD --> DB
    MIG --> DB
```

### Qué va en cada capa y qué no

| Capa | Responsabilidad | No debe contener |
|---|---|---|
| Presentación | Qué se ve: plantillas, estilos, JavaScript de la pantalla | Reglas de negocio ni consultas a la base |
| Vistas | Recibir la solicitud, validar el formulario, verificar permisos, llamar al servicio y devolver la respuesta | Cálculos ni reglas del negocio |
| Servicios | Reglas de negocio y casos de uso (por ejemplo, abrir caja, registrar venta, registrar pago). Cada operación que toca varias tablas corre en una transacción | Detalles de pantalla (HTML, formularios) |
| Acceso a datos | Modelos, restricciones, migraciones y consultas | Reglas que dependen del caso de uso |

**Regla de dependencia:** cada capa solo llama a la inmediatamente inferior. Con esto las reglas del negocio (RN-xx y RI-xx) se prueban sin abrir el navegador y cada pantalla las reutiliza. En la práctica:

- Las vistas no consultan los modelos: piden los datos a un servicio (por ejemplo, `obtener_venta`, `caja_cerrada`, `producto_editable`) y solo convierten "no existe" en una respuesta 404.
- Las plantillas no deciden reglas: reciben el resultado ya calculado (por ejemplo, `puede_anularse` o `de_otro_dia`).
- Los formularios validan el formato de los datos; las reglas las aplica el servicio.

**Permisos en dos lugares:** la vista verifica que el rol tenga la función del menú (`requiere_funcion`, en `apps/comun/permisos.py`) y el servicio vuelve a verificar el permiso antes de operar (`PermissionDenied`). La segunda verificación protege la regla aunque el servicio se llame desde otra pantalla, el panel o una prueba. Cuando el menú depende de una regla de negocio (por ejemplo, RN-05 para la cajera con permiso de alta), usa la función del servicio en lugar de repetirla.

**Dependencias entre módulos:** un servicio puede usar los servicios de otro módulo solo en un sentido, sin ciclos:

```mermaid
flowchart LR
    ventas --> caja
    ventas --> catalogo
    caja --> usuarios
    catalogo --> usuarios
    ventas --> usuarios
    comun --> caja
    comun --> catalogo
    comun --> ventas
    comun --> usuarios
```

`caja` y `catalogo` nunca importan servicios de `ventas`. `comun` depende de los otros módulos solo para la navegación y el inicio (menú, permisos y resumen del día); ningún módulo de negocio depende de `comun` salvo por el modelo base y `requiere_funcion`. Las relaciones entre modelos de distintos módulos (por ejemplo, `venta` y `movimiento_caja` se referencian mutuamente) son parte del modelo de datos ([05-modelo-datos.md](05-modelo-datos.md)) y no cuentan como dependencia entre servicios.

## 4. Módulos y su relación con el modelo

Cada módulo es una aplicación del proyecto. Los nombres son una propuesta.

| Módulo | Entidades ([05-modelo-datos.md](05-modelo-datos.md)) | Casos de uso |
|---|---|---|
| `usuarios` | `usuario` | CU-10, CU-14 |
| `caja` | `caja`, `cierre_caja_detalle`, `movimiento_caja`, `medio_pago` | CU-02, CU-03, SC-02 |
| `ventas` | `venta`, `detalle_venta` | CU-01, SC-03, SC-04 |
| `catalogo` | `categoria`, `producto` | CU-06, CU-11 |
| `proveedores` | `proveedor`, `producto_proveedor`, `ingreso_mercaderia`, `detalle_ingreso`, `pago_proveedor` | CU-05, CU-07, CU-13 |
| `clientes` | `cliente`, `pago_cliente`, `movimiento_cuenta_corriente` | CU-04, CU-08, CU-12, SC-01 |
| `reportes` | (consultas sobre las anteriores; la aplicación se crea en H5) | CU-09 |
| `comun` | Ninguna propia: el modelo base abstracto con `creado_en` y `actualizado_en` que heredan todas las entidades. Además reúne la navegación: menú y permisos por rol (`menu.py`, `permisos.py` y el procesador de contexto del menú), la pantalla de inicio y los datos de ejemplo con el comando `cargar_datos_ejemplo` | CU-10 (inicio después de ingresar) |

### Estructura propuesta del repositorio

```
sistema-gestion-carniceria/
├── README.md
├── docs/                      documentación (fuente de verdad)
│   └── specs/                 specs de cada caso de uso o etapa (SPEC-CU-xx)
├── config/                    configuración del proyecto
├── .github/workflows/         GitHub Actions: ruff y pytest en cada Pull Request
├── apps/
│   ├── comun/                 modelo base, menú y permisos por rol, inicio, datos de ejemplo
│   │   └── management/commands/   cargar_datos_ejemplo
│   └── <módulo>/              usuarios, caja, ventas, catalogo, proveedores, clientes
│       ├── models.py          capa de acceso a datos
│       ├── migrations/
│       ├── services.py        capa de servicios (reglas de negocio)
│       ├── views.py           capa de vistas
│       ├── forms.py
│       ├── urls.py
│       ├── admin.py           registro en el panel de administración
│       └── tests/             pruebas de pytest; tests/js/ para las de JavaScript (node --test)
├── templates/                 plantillas HTML, una carpeta por módulo
├── static/
│   ├── src/                   estilos de entrada de Tailwind
│   ├── css/                   estilos compilados
│   └── js/                    JavaScript de las pantallas
├── locale/                    traducciones al español
├── manage.py
├── conftest.py                datos ficticios compartidos por las pruebas
├── pyproject.toml             configuración de ruff y pytest
├── requirements.txt           dependencias con versión fija
├── package.json               Tailwind CLI (npm run estilos)
├── .env.example               plantilla: solo nombres y valores de ejemplo
├── CLAUDE.md                  instrucciones para Claude Code
└── .claude/settings.json      permisos de Claude Code
```

Hoy `proveedores` y `clientes` solo tienen modelos (sus servicios y pantallas llegan en H3 y H4), y `reportes` todavía no existe (H5). La estructura se ajusta durante el desarrollo; lo importante es que cada módulo mantenga las capas separadas y sus pruebas junto al código.

## 5. Entorno local

```mermaid
flowchart LR
    CH[Chrome] -->|http local| DJ[Servidor de desarrollo de Django]
    DJ --> PG[(PostgreSQL local)]
    TWC[Tailwind CLI] -->|compila estilos| ST[static/css]
    ST --> DJ
    PT[pytest] --> DJ
    PT --> PGT[(Base de datos de prueba)]
```

Necesita instalarse en la computadora del alumno:

| Herramienta | Para qué |
|---|---|
| Python (versión estable vigente) con entorno virtual | Ejecutar Django |
| PostgreSQL | Base de datos de desarrollo y de prueba |
| Git | Ya instalado |
| Tailwind CLI | Compilar los estilos |
| Claude Code | Agente de desarrollo, cuando corresponda |

La guía de instalación paso a paso va en el `README.md` del repositorio.

## 6. Primer hito: base funcionando en local

El objetivo de esta etapa es tener la base de datos, el back y el front funcionando juntos, antes de construir los módulos completos.

| Paso | Contenido | Se verifica cuando |
|---|---|---|
| H1.1 | Proyecto Django configurado con PostgreSQL local y variables de entorno | El servidor arranca y conecta a la base |
| H1.2 | Modelos y migraciones de las 17 entidades de [05-modelo-datos.md](05-modelo-datos.md), con sus restricciones `UNIQUE`, `CHECK` y claves foráneas | Las migraciones se aplican en una base vacía |
| H1.3 | Datos de ejemplo cargables con un comando (sin datos reales) | Hay productos, clientes y usuarios de prueba |
| H1.4 | Tailwind configurado y plantilla base responsive con menú según el rol (`templates/base.html`, `apps/comun/menu.py`; estilo en DEC-30) | La página se ve bien en PC y en celular |
| H1.5 | Inicio y cierre de sesión con permisos por rol (CU-10; RF-01, RF-02) | Cada rol ve solo sus funciones |
| H1.6 | Un caso de uso completo de punta a punta que atraviese todas las capas: **CU-11 Gestionar productos** (alta, modificación y baja lógica) | Se puede crear y editar un producto desde la pantalla y queda en la base |
| H1.7 | `pytest` funcionando con la base de datos de prueba y las primeras pruebas de reglas de integridad | Las pruebas pasan |

CU-11 se elige para el hito porque no depende de otros casos de uso y ejercita todas las capas. Los hitos siguientes (caja y venta, stock y proveedores, clientes y cuentas corrientes, reportes) se ordenan en [07-planificacion.md](07-planificacion.md).

### Credenciales de la base local y salvaguardas (D-14)

**Decisión:** el agente (hoy Claude Code; Codex se suma más adelante) puede correr pruebas contra una base local de prueba con datos ficticios, sin acceso a secretos reales.

| Elemento | Tratamiento |
|---|---|
| `.env.example` | Se sube al repo. Solo nombres de variables y valores de ejemplo, nunca secretos |
| `.env` | Local, ignorado por Git (`.env`, `.env.*`, salvo `.env.example`). Los agentes no lo leen |
| Base de pruebas | PostgreSQL local con usuario y contraseña exclusivos de desarrollo y datos ficticios |
| Cómo se conectan las pruebas | Django lee el `.env` por su cuenta; el agente ejecuta `pytest` sin necesitar ver el contenido |
| Secretos reales (producción, correo, servicios externos) | Nunca en el repo ni en la computadora de desarrollo hasta que existan; se tratan al definir el despliegue |
| Configuración | Por ahora solo Claude Code: `CLAUDE.md` y `.claude/settings.json` con lectura denegada sobre secretos. Al sumar Codex se agrega `AGENTS.md` como fuente única y su propia configuración de permisos |

**Límite conocido:** las reglas de lectura de los agentes no alcanzan a los procesos que ellos lancen (un script podría leer el `.env`). Se acepta porque las credenciales locales son descartables y no abren nada fuera de la base de pruebas. Si más adelante hubiera secretos con valor, se agrega un entorno aislado (sandbox o contenedor).

## 7. Recomendaciones técnicas

| Tema | Recomendación |
|---|---|
| Dinero y cantidades | `DecimalField` con dos decimales para montos; nunca `float` |
| Transacciones | Cada servicio que toca varias tablas usa una transacción atómica (RNF-10) |
| Zona horaria | Guardar en UTC y mostrar en hora local |
| Panel de administración de Django | Útil para el alta inicial de datos y para el administrador, pero la cajera usa pantallas propias. Usa el tema django-unfold con el estilo del sistema (DEC-30). Desde H1 todos los modelos están registrados; el primer administrador se crea con `createsuperuser` (ver `README.md`). Los registros operativos (cajas, cierres, movimientos de caja, ventas, pagos, ingresos y movimientos de cuenta corriente) se consultan en el panel pero no se cargan, modifican ni borran ahí: se crean solo desde su caso de uso, que aplica las reglas en una transacción (DEC-31). Los formularios repiten los límites de la base (no negativo, mayor a 0) para mostrar el error junto al campo |
| Datos de ejemplo | Un comando que carga datos ficticios, para desarrollar y probar sin datos reales |
| Formato del código | Una herramienta automática de formato y análisis, ejecutada antes de cada commit: `ruff` (configurado en `pyproject.toml`) |
| Reglas de negocio | Cada regla RN-xx o RI-xx con al menos una prueba automática |
| Documentación | Todo cambio de código actualiza los archivos afectados de `/docs` |

## 8. Seguridad

| Aspecto | Decisión |
|---|---|
| Contraseñas | Con el sistema de hash del framework, nunca en texto plano (RNF-07) |
| Permisos | Por rol y por función; Dueños solo ven reportes; la cajera solo ve sus funciones (RF-02). Cada pantalla se protege con `requiere_funcion`, que usa la tabla del menú: sin sesión redirige al ingreso y sin permiso responde 403. El panel de Django es solo para el Administrador (DEC-32). Qué ve la cajera en el inicio está a confirmar (PR-35) |
| Sesiones | Cookies protegidas y cierre por inactividad. El tiempo está a confirmar (PR-34); mientras tanto queda el valor por defecto de Django (dos semanas). Salir cierra la sesión en el servidor |
| Formularios | Protección contra falsificación de solicitudes del framework |
| Base de datos | Consultas por el ORM, que evita la inyección SQL |
| Secretos | Variables de entorno; el repositorio solo incluye `.env.example` sin secretos (RE-02, D-14) |
| Datos de clientes | Acceso restringido por rol (RNF-08) |
| Intentos de ingreso | Se evaluará limitar los intentos fallidos antes del uso real |

## 9. Despliegue (diferido)

Por decisión del alumno, en esta etapa no se preparan archivos de despliegue. Cuando se retome, la plataforma de alojamiento deberá cumplir estas condiciones, sin ligarse a un proveedor en particular:

- Conexión segura por HTTPS.
- PostgreSQL con copias automáticas y posibilidad de restaurar.
- Despliegue desde el repositorio de GitHub.
- Variables de entorno para claves y configuración.
- Costo acorde al presupuesto del negocio (PR-33).
- Archivos estáticos versionados (por ejemplo, con un hash en el nombre, como hace `ManifestStaticFilesStorage` de Django), para que el navegador no siga usando un JavaScript o CSS viejo después de una actualización. Pendiente: en el recorrido de la etapa 4 de H2 el navegador tenía en caché el `venta.js` anterior y no mostraba "Crear producto" hasta recargarlo sin caché (registro de recorridos de 08).

El proveedor y el costo se verifican con los planes vigentes al decidir. Si la cátedra solo exige una demostración local (PA-05), el despliegue puede no ser parte de la entrega.

## 10. Decisiones diferidas

Se postergan a propósito. Se reevalúan durante el desarrollo.

| Tema | Cuándo se reevalúa |
|---|---|
| Despliegue y alojamiento | Cuando el sistema funcione en local y se defina PA-05 |
| Copias de seguridad automáticas | Junto con el despliegue |
| Versionado de archivos estáticos (sección 9) | Junto con el despliegue |
| Reportes PDF y Excel | Al llegar a CU-09 |
| Libro de movimientos de stock | Si aparecen diferencias de stock (ver [05-modelo-datos.md](05-modelo-datos.md)) |
| API con JWT y aplicación móvil | Si hace falta un cliente que no sea el navegador |
| Modo sin conexión | Según PR-29 |
| Impresora térmica de tickets | El ticket se imprime desde el navegador (DEC-44); una impresora térmica sirve sin integración |
| Docker | Si la instalación local resulta engorrosa |
| Limitación de intentos de ingreso | Antes del uso real |

## 11. Riesgos técnicos

| ID | Riesgo | Mitigación |
|---|---|---|
| RT-01 | Caída de internet en el local | Definir contingencia mínima (PR-29); modo sin conexión diferido |
| RT-02 | Pérdida de datos | Copias automáticas al desplegar (D-08) |
| RT-03 | Costo del alojamiento no sostenible | Validar presupuesto (PR-33) antes de elegir proveedor |
| RT-04 | El agente introduce cambios sin pruebas | Pull Request obligatorio, pruebas automáticas y reglas en `CLAUDE.md` |
| RT-05 | Reglas de negocio mezcladas con las pantallas | Capa de servicios y pruebas de reglas |
| RT-06 | Poco conocimiento repartido del sistema | Documentación actualizada en `/docs` y pruebas que explican el comportamiento |
| RT-07 | El inicio de sesión no limita los intentos fallidos: se puede probar contraseñas sin freno (fuerza bruta) | En local el riesgo es bajo. Si el sistema se despliega (PA-05), agregar un límite de intentos por usuario y por dirección antes de publicarlo |

## 12. Preguntas pendientes que afectan esta arquitectura

| Brecha | Impacto |
|---|---|
| PR-33 | Costo y elección del alojamiento |
| PA-05 | Si el despliegue es parte de la entrega; si lo es, antes hay que limitar los intentos de inicio de sesión (RT-07) |
| PR-23 | Cantidad de usuarios y dispositivos |
| PR-29 | Contingencia ante caída de internet |
| PR-34 | Tiempo de cierre de sesión por inactividad |
| PR-35 | Qué ve la cajera en el inicio (total del día y últimas ventas, o solo su caja) |

## 13. Mantenimiento

Al cambiar una decisión técnica, actualizar este documento y registrar el motivo en [09-decisiones.md](09-decisiones.md); revisar el impacto en [05-modelo-datos.md](05-modelo-datos.md), en [08-pruebas.md](08-pruebas.md) y en `CLAUDE.md`.
