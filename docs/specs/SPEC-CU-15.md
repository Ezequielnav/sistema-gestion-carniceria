# SPEC - CU-15 Ajustar stock (H3, etapa 1b)

**Estado:** aprobado (pedido del alumno, 2026-10-29).

Fuente de verdad: `/docs`. Este spec no agrega reglas: las toma de CU-15 y CU-11 (04), RF-50 y RF-51 (03), RI-07 y RI-17 (05), DEC-31, DEC-33, DEC-79, DEC-96 y DEC-98 a DEC-100 (09) y los casos CP-73 y CP-107 a CP-109 (08). DEC-98, DEC-99 y DEC-100 son **supuestos del proyecto, no datos confirmados por el negocio** (PR-32 se cerró como supuesto).

## 1. Objetivo

El Administrador corrige el stock de un producto con el stock real contado y un motivo, y el sistema deja registrado cada ajuste. El alta del Administrador puede cargar un stock inicial, que queda registrado igual. El stock solo cambia por operaciones con registro: el panel no da de alta productos ni edita el stock.

**Usuario:** el rol Administrador. La cajera y los dueños no ajustan (403); la cajera con permiso de alta no ve el stock inicial (DEC-33).

**Reglas:**

| Regla | Origen |
|---|---|
| "Ajustar stock" solo en productos activos con control de stock; otro producto da 404 por URL directa | DEC-98, CU-15 A3 |
| Stock contado mayor o igual a 0; entero por `UNIDAD`, hasta 3 decimales por `KG`. Mismo formato que `validar_cantidad`, pero admite 0 | DEC-79, DEC-98, RI-17 |
| Motivo obligatorio: conteo, vencimiento, rotura u otro; observación opcional (hasta 255), obligatoria con "otro" | DEC-98 |
| En una transacción, con el producto bloqueado (`select_for_update`): stock anterior = stock del momento; `mover_stock(producto, contado - anterior)`; se crea `ajuste_stock`. Un contado igual al stock se registra igual | RI-07, RI-17, DEC-96, DEC-98 |
| Los ajustes no se editan ni se borran (ni en pantalla ni en el panel) | RI-17, DEC-100 |
| Alta del Administrador en `/productos/nuevo/`: campo opcional "Stock inicial", mismo formato; solo con control de stock (si no, error junto al campo). Si es mayor a 0, en la misma transacción que el alta: `mover_stock` y ajuste `STOCK_INICIAL` con anterior 0. El servicio rechaza un stock inicial de quien no es Administrador | DEC-99 |
| La cajera con permiso (y el alta desde la venta) no tienen el campo: su alta arranca en 0 | DEC-33, DEC-99 |
| Panel: `Producto` sin alta (403) y con `stock_actual` de solo lectura; `AjusteStock` como registro operativo de solo lectura, en el menú "Catálogo" | DEC-31, DEC-100 |

**Criterios de aceptación:**
1. Un aceite con stock 10 ajustado a 7 por rotura queda en 7 y deja un ajuste con anterior 10, nuevo 7, motivo, usuario y fecha (CP-107).
2. -1, 1,5 en un producto por unidad o 0,0005 kg se rechazan junto al campo; "otro" sin observación se rechaza; el stock no cambia (CP-107).
3. Un contado igual al stock se registra sin cambiar el stock (CP-107).
4. La cajera y los dueños reciben 403; un producto sin control de stock o dado de baja, 404 (CP-107).
5. Alta del Administrador con stock inicial 12: stock 12 y ajuste `STOCK_INICIAL` 0 → 12; sin valor, 0 sin ajuste; sin control de stock, error junto al campo. La cajera con permiso no ve el campo y si lo envía su alta queda en 0 (CP-108).
6. En el panel, el alta de productos da 403 y `ajuste_stock` se lista pero no se carga, modifica ni borra (CP-109).
7. `ajuste_stock` existe con auditoría, sus `CHECK` y su índice (CP-73).

## 2. Comandos

```bash
.venv/bin/python manage.py makemigrations catalogo   # una migración: tabla ajuste_stock
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest
```

## 3. Estructura

| Archivo | Cambio |
|---|---|
| `apps/catalogo/models.py` | `MotivoAjuste` y `AjusteStock` (tabla `ajuste_stock`) |
| `apps/catalogo/services.py` | `validar_stock_contado`, `ajustar_stock`; `crear_producto` con `stock_inicial` |
| `apps/catalogo/forms.py`, `views.py`, `urls.py` | `AjusteStockForm`, `/productos/<pk>/ajustar/`, campo "Stock inicial" solo para el Administrador |
| `templates/catalogo/` | `ajuste_form.html`; botón "Ajustar stock" en el listado; campo en el alta |
| `apps/catalogo/admin.py`, `config/settings.py` | Producto sin alta; `AjusteStockAdmin` de solo lectura; ítem del menú |

## 4. Pruebas

Servicio y pantalla por cada criterio, permisos con 403, panel (CP-109) y estructura (CP-73). Recorrido en localhost con un usuario temporal.

## 5. Límites

- **Siempre:** rama `h3`; `mover_stock` como única forma de cambiar el stock; docs al día en el mismo commit.
- **Nunca:** editar o borrar ajustes; mostrar el stock a la cajera; push sin pedido.
- **Fuera de este spec:** historial de ajustes en pantalla (se consulta en el panel), `movimiento_stock` (DEC-24), aviso en la venta (DEC-102, etapa 5).
