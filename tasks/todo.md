# Estado de H2 (caja y ventas) - para retomar en una sesión nueva

Rama de trabajo: `feat/h2-caja-ventas`, creada desde `main`. Etapas en `docs/07-planificacion.md` ("Etapas de H2").

## Hecho

- [x] Etapa 1 - Abrir caja (CU-02): `/caja/`, una caja por fecha y turno y una sola abierta (DEC-38, DEC-39). Spec: `docs/specs/SPEC-CU-02.md`. En `main` con el PR #11.
- [x] Etapa 2 - Registrar venta (CU-01): `/ventas/nueva/`, búsqueda y lector, confirmación en el servidor, ticket (DEC-36 a DEC-54). Spec: `docs/specs/SPEC-CU-01.md`. En `main` con el PR #11.
- [x] Etapa 3 - Cerrar caja (CU-03) y egresos "otros" (SC-02, DEC-43): `/caja/egreso/`, `/caja/cerrar/` y `/caja/<id>/cierre/`, `medio_pago.es_efectivo` (DEC-55 a DEC-61). Spec: `docs/specs/SPEC-CU-03.md`. Recorrido RM-03 hecho con Playwright (registro en 08).

## Falta: etapa 4 (cierre de H2)

- [ ] Alta de producto durante la venta (CU-01 A1, RF-17, RN-05): la cajera con permiso crea el producto desde la pantalla de venta reusando el servicio de CU-11. Automatizar CP-56 "durante la venta".
- [ ] Anulación de ventas (DEC-45): el Administrador anula, con motivo, una venta de la caja abierta; reversa de caja y stock en una sola operación. Requiere un estado en `venta` (migración) y CP-85. Hacer `/spec` antes (en `docs/specs/`).
- [ ] Recorrido RM-04 (venta en pocos pasos con lector y búsqueda) anotado en el registro de recorridos de 08. Se probó en la etapa 2, pero no quedó registrado.
- [ ] `/review` de todo H2, docs al día (04, 05, 07, 08, 09) y PR de cierre del hito.

## Para tener en cuenta

- Preguntas que siguen abiertas: PR-02 (reportes de Kendra) y PR-35 (qué ve la cajera en el inicio), más PA-02 y PA-03 (cátedra).
- Base de desarrollo: migraciones hasta `caja/0005` aplicadas. No hay cajas abiertas; las del 25/10 y 26/10 están cerradas con sus cierres. El aceite de girasol está dado de baja; no se sabe quién lo dio de baja.
- Servidor local: `.claude/launch.json` (configuración `django`, puerto 8000), fuera del repositorio por `.gitignore`.
- Antes de cada PR: `python manage.py check`, `makemigrations --check`, `ruff check .`, `ruff format --check .` y `pytest`.
