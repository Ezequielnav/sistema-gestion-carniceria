# Plan - Etapa 3 de H2: egresos "otros" y cierre de caja (CU-03)

Fuente: `docs/specs/SPEC-CU-03.md` (aprobado, DEC-55 a DEC-61). Plan completo; el estado de H2 y lo que falta está en `tasks/todo.md`.

## Dependencias

```
medio_pago.es_efectivo (DEC-55, migración caja/0005, datos de ejemplo)
        ├── A. Egresos "otros": servicio + formulario en la pantalla de Caja
        └── B. Cierre: esperado por medio, cierre, bloqueo
                    └── Pantallas de cierre y reporte
                            └── Docs, verificación y RM-03 con Playwright
```

## Tareas

### T1. Efectivo identificado (DEC-55)
- `MedioPago.es_efectivo` con un único parcial `medio_pago_un_solo_efectivo`; migración `caja/0005` que marca el medio "Efectivo" existente. Datos de ejemplo, panel y fixture `efectivo` de las pruebas.
- **Acepta:** la base rechaza dos medios en efectivo; la migración marca "Efectivo".
- **Verifica:** `pytest apps/caja apps/comun`, `makemigrations --check`.

### T2. Egresos "otros" (módulo A)
- Servicio `registrar_egreso_otro` (DEC-43, DEC-57, RI-13), formulario y `/caja/egreso/`; lista de egresos en la pantalla de Caja (DEC-58).
- **Acepta:** CP-81; sin descripción, monto no positivo, sin caja o por encima del efectivo disponible se rechaza.
- **Verifica:** `pytest apps/caja`.

### Punto de control 1
Efectivo y egresos en verde.

### T3. Cierre de caja (módulo B)
- `resumen_de_cierre` (DEC-38, DEC-56) y `cerrar_caja` (RI-10, DEC-40, RN-03, RNF-10) con bloqueo de la fila; `/caja/cerrar/` y `/caja/<id>/cierre/` (DEC-59, DEC-60); botón "Cerrar caja".
- **Acepta:** CP-04 a CP-07; caja cerrada sin ventas ni egresos; reporte visible para cajera, Administrador y Dueños.
- **Verifica:** `pytest`.

### T4. Docs y verificación
- 04, 05, 07 y 08. `check`, `makemigrations --check`, `ruff`, `pytest`.

### T5. RM-03 con Playwright en localhost
- Migrar la base de desarrollo, completar la caja de la mañana (tercera venta con otro medio y un egreso) y cerrarla con una diferencia y su motivo. Revisar el reporte como cajera, Administrador y Dueño.

### Punto de control 2
Todo en verde, sin commit.
