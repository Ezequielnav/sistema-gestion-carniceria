# SPEC - CU-02 Abrir caja por turno (H2, etapa 1)

**Estado:** aprobado.

Fuente de verdad: `/docs`. Este spec no agrega reglas: las toma de CU-02 (04), RF-04, RF-05 y RF-10 (03), RN-01 y RN-02 (04), RI-01 (05), DEC-38 y DEC-39 (09), y de los casos CP-01 a CP-03, CP-07, CP-79 y CP-80 (08).

## 1. Objetivo

La cajera abre la caja de su turno para empezar a vender. Todo lo demás de H2 (venta, movimientos y cierre) necesita una caja abierta.

**Usuario:** solo el rol Cajera, con o sin permiso de alta de productos. Según la matriz de actores de 04, el Administrador y los Dueños no abren la caja.

**Reglas:**

| Regla | Origen |
|---|---|
| La cajera elige el turno: mañana o tarde. El formulario ofrece solo los turnos que todavía se pueden abrir ese día; si no queda ninguno, no muestra el formulario y lo avisa. El servicio igual rechaza un turno inválido o ya usado | RF-04, RN-02, DEC-39 |
| La caja se crea con la fecha local de hoy, el turno, la cajera que la abre, el estado `ABIERTA` y la hora de apertura | RF-04 |
| Puede cargar un fondo de cambio en efectivo. Es opcional y no puede ser negativo. Si lo deja vacío, se guarda 0 | RF-10, DEC-38 |
| No se abre si ya hay otra caja abierta, de cualquier turno o fecha. El mensaje dice cuál está abierta y pide cerrarla | RF-05, RN-01, DEC-39, CU-02 A1 y A3 |
| No se abre un turno que ya tuvo caja ese día, aunque esté cerrada | DEC-39, CU-02 A4 |
| Si dos cajeras abren a la vez, la base rechaza la segunda y se muestra el mismo mensaje claro, no un error 500 | RI-01 |

**Criterios de aceptación:**
1. Sin ninguna caja abierta, una cajera abre "Mañana" con o sin fondo y ve un aviso de que la caja se abrió (CP-01, CP-07).
2. Con una caja abierta, abrir otra (del mismo turno o del otro) se rechaza con un mensaje que nombra la caja abierta (CP-02, CP-79).
3. Con la caja de la mañana de hoy ya cerrada, el formulario ofrece solo "Tarde" y abrir "Mañana" por el servicio se rechaza (CP-80). Abrir "Tarde" se permite.
4. Un turno inválido o un fondo negativo se rechazan con el mensaje junto al campo (CP-03, RI-16).
5. El Administrador, los Dueños y quien no inició sesión no acceden: 403, o la pantalla de ingreso si no hay sesión.
6. El menú de la cajera muestra "Caja" con su enlace. Ya no aparece como "Pronto".

## 2. Comandos

```bash
source .venv/bin/activate
python manage.py makemigrations caja        # una sola migración: cambio de restricciones de RI-01
python manage.py check
python manage.py makemigrations --check --dry-run
ruff check . && ruff format --check .
pytest
```

## 3. Estructura

Se siguen las capas de 06 (vistas, servicios y acceso a datos) y el mismo patrón de CU-11.

| Archivo | Cambio |
|---|---|
| `apps/caja/models.py` | RI-01 según DEC-39: en lugar del único parcial `caja_abierta_unica_por_fecha_turno`, `UNIQUE (fecha, turno)` (`caja_unica_por_fecha_turno`) y un único parcial sobre `estado` cuando `estado = 'ABIERTA'` (`caja_una_sola_abierta`), con mensajes en español |
| `apps/caja/migrations/0004_...` | Esa migración. Antes de aplicarla en la base de desarrollo, revisar que no haya dos cajas abiertas ni dos cajas con la misma fecha y turno; si las hay, la migración falla y avisa |
| `apps/caja/services.py` | `puede_abrir(usuario)`, `caja_abierta()` (la única abierta o `None`) y `abrir_caja(usuario, turno, monto_inicial)`. Esta última valida, guarda en un savepoint y convierte el `IntegrityError` de las dos restricciones en `ValidationError` con mensaje claro. `cajas_abiertas()` sigue igual para el inicio |
| `apps/caja/forms.py` | `AbrirCajaForm`: el turno con la primera opción "Elegí un turno" (como "Elegí una unidad" en productos) y solo los turnos que se pueden abrir, y el fondo de cambio opcional con `min="0"` (vacío se guarda 0) |
| `apps/caja/views.py` | `caja` (GET: estado; POST: abrir), con `@requiere_funcion("Caja")` |
| `apps/caja/urls.py` y `config/urls.py` | `caja/` → `caja:caja` |
| `apps/comun/menu.py` | `Funcion("Caja", ..., url="caja:caja")` |
| `templates/caja/caja.html` | Si hay una caja abierta, muestra sus datos (fecha, turno, quién la abrió, hora, fondo). Si no la hay, muestra el formulario de apertura con los turnos que se pueden abrir; si no queda ninguno, avisa que ya se usaron los dos turnos del día. Si la caja abierta es de otra fecha, un aviso pide cerrarla. El botón "Cerrar caja" llega en la etapa 3 |
| `apps/caja/tests/test_servicios_caja.py` y `test_pantalla_caja.py` | Pruebas nuevas (sección 5) |
| `apps/comun/tests/test_estructura.py` | Se actualizan los nombres de las restricciones de `caja` (CP-73) |

Al terminar se actualizan los docs: 04 (nota de implementación de CU-02), 05 (sacar la aclaración "la base todavía tiene el índice anterior" de 7.4), 08 (CP-01 a CP-03, CP-07, CP-79 y CP-80 automatizados) y 06 si cambia algo del módulo `caja`.

## 4. Estilo de código

- Igual que `apps/catalogo`:
  - Las reglas viven en el servicio. El formulario solo arma los campos.
  - La vista llama al servicio y pasa sus `ValidationError` al formulario.
  - Textos en español, nombres en español y comentarios cortos que citan la regla (RN-xx, RI-xx, DEC-xx).
- Dinero con `campo_monto` (`DecimalField`), nunca `float`.
- La fecha sale de `timezone.localdate()`. El turno lo elige la cajera: no se deduce de la hora, porque no hay horarios definidos (DEC-39).
- La interfaz usa los mismos componentes de Tailwind que la pantalla de productos (DEC-30). El prototipo v0 es solo una guía funcional (DEC-07).

## 5. Pruebas

| Prueba | Nivel | Caso |
|---|---|---|
| Abre "Mañana" sin fondo: estado, fecha, turno, usuario y hora | Servicio | CP-01 |
| Abre con fondo de 5000,00; el fondo vacío se guarda 0; el fondo negativo se rechaza | Servicio | CP-07, RI-16 |
| El formulario ofrece solo los turnos libres del día; con los dos usados, no se muestra | Pantalla | DEC-39 |
| Con "Mañana" abierta, abrir "Mañana" o "Tarde" se rechaza con un mensaje que nombra la caja abierta | Servicio | CP-02, CP-79 |
| Con "Mañana" de hoy cerrada, abrir "Mañana" se rechaza y abrir "Tarde" se permite | Servicio | CP-80 |
| Una caja abierta de ayer impide abrir hoy | Servicio | DEC-39 |
| Guardado simultáneo: con la verificación previa simulada, la base rechaza la caja y sale el mismo mensaje (mismo patrón que CP-59) | Servicio | RI-01 |
| La base rechaza dos cajas abiertas y dos cajas con la misma fecha y turno | Integridad | CP-02, CP-73 |
| Turno inválido rechazado | Integridad (ya existe) | CP-03 |
| La cajera, con o sin permiso de alta, ve el formulario, abre la caja y después ve su estado | Pantalla | RF-04 |
| Errores junto al campo y sin errores 500 | Pantalla | CU-02 A1 |
| Administrador y Dueño reciben 403; sin sesión, se redirige al ingreso | Pantalla | RF-02, RNF-06 |
| El menú de la cajera muestra "Caja" con su enlace | Pantalla | CP-74 |

Recorrido manual con Playwright en localhost y datos de ejemplo: la cajera abre "Mañana" con fondo, intenta abrir "Tarde" y ve el rechazo. Es parte de RM-03, que se completa en la etapa 3.

## 6. Límites

**Siempre:**
- Correr check, ruff y pytest antes de proponer el cambio.
- Poner cada regla en el servicio, con su prueba.
- Actualizar `/docs` en el mismo cambio.

**Preguntar antes:**
- Cualquier regla que no esté en esta tabla, como deducir el turno por la hora o dejar abrir al Administrador.
- Aplicar la migración sobre una base de desarrollo que tenga cajas que la violen.
- Hacer commit.

**Nunca:**
- Abrir la caja desde el panel: es de solo lectura (DEC-31).
- Usar `float` para el fondo.
- Leer `.env`.
- Usar datos reales.

**Fuera de esta etapa:** cerrar la caja (CU-03), los egresos "otros" (DEC-43) y las ventas. Mientras no exista CU-03, una caja abierta solo se puede cerrar recreando los datos de ejemplo. Es un límite conocido entre la etapa 1 y la etapa 3.

## Decisiones del spec

1. **Fondo vacío:** se guarda 0 (DEC-38).
2. **Turnos:** el formulario muestra solo los turnos que se pueden abrir; el servicio igual lo valida (DEC-39).
