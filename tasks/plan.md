# Plan - CU-01 Registrar venta (H2, etapa 2)

Fuente: `docs/specs/SPEC-CU-01.md` (aprobado, DEC-47 a DEC-54). El plan de CU-02 (etapa 1) quedó completo.

## Dependencias

```
SC-02: registrar_ingreso_venta (caja)
        └── registrar_venta (ventas): validación, precios, stock, transacción
                ├── buscar_para_venta + JSON /ventas/buscar/
                └── Pantalla /ventas/nueva/ + venta.js + confirmar + ticket
                        └── Docs y recorrido con Playwright
```

## Tareas

### T1. Registrar una venta (servicio de punta a punta)
- `caja.services.registrar_ingreso_venta(venta)` (SC-02, RI-02, RI-04, RI-13).
- `ventas.services`: `puede_vender`, `medios_de_pago_para_venta`, `registrar_venta(usuario, lineas, medio_pago)` con `transaction.atomic()`, precios desde la base, DEC-48 a DEC-50, DEC-53 (líneas repetidas se suman), stock con `F()` y avisos de DEC-46.
- **Acepta:** CP-10 a CP-17, CP-20, CP-21, CP-83.
- **Verifica:** `pytest apps/ventas apps/caja`.

### T2. Búsqueda para la venta
- `buscar_para_venta(texto)`: activos, nombre que contiene o plus exacto; marca si hubo coincidencia exacta de plus (DEC-52). Vista JSON `/ventas/buscar/`.
- **Acepta:** CP-82; inactivos excluidos.
- **Verifica:** `pytest apps/ventas`.

### Punto de control 1
Servicios y búsqueda en verde.

### T3. Pantalla de venta, confirmación y ticket
- `/ventas/nueva/` (sin caja abierta o con caja de otro día: aviso y enlace a Caja), `static/js/venta.js` (lista en el navegador, DEC-47, DEC-51 a DEC-53), `/ventas/confirmar/` (POST, recalcula en el servidor) y `/ventas/<id>/ticket/` (DEC-44, DEC-54). Menú "Ventas".
- **Acepta:** venta completa desde la pantalla, ticket con la leyenda, permisos por rol, datos manipulados del navegador ignorados.
- **Verifica:** `pytest`, `npm run estilos`.

### T4. Docs y verificación
- 04 (implementación de CU-01), 05 (si corresponde), 08 (casos automatizados).
- `check`, `makemigrations --check`, `ruff`, `pytest`.

### T5. Recorrido con Playwright en localhost
- Con la caja abierta: venta con carne por kg (sin stock), un producto por unidad con stock suficiente y uno con stock insuficiente, en dos ventas con dos medios de pago distintos. Revisar ticket, caja y stock en la base.

### Punto de control 2
Todo en verde, sin commit.
