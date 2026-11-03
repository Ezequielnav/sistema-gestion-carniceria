# SPEC - Stock editable en CU-11 (H3, etapa 1b)

**Estado:** aprobado (pedido del alumno, 2026-10-29). Reemplaza el primer diseño del mismo día, que tenía un caso de uso aparte (CU-15 Ajustar stock, integrado a CU-11).

Fuente de verdad: `/docs`. Este spec no agrega reglas: las toma de CU-11 (04), RF-50 y RF-51 (03), RI-07 y RI-17 (05), DEC-31, DEC-33, DEC-79, DEC-96 y DEC-98 a DEC-100 (09) y los casos CP-73 y CP-107 a CP-109 (08). DEC-98, DEC-99 y DEC-100 son **supuestos del proyecto, no datos confirmados por el negocio** (PR-32 se cerró como supuesto).

## 1. Objetivo

El Administrador carga y corrige el stock al crear o modificar un producto, en `/productos/` o en el panel, y cada cambio queda registrado. No hay una pantalla de ajuste aparte.

**Usuario:** el rol Administrador. La cajera con permiso de alta no ve el stock (DEC-33).

**Reglas:**

| Regla | Origen |
|---|---|
| El stock se edita solo en productos que controlan stock: mayor o igual a 0; entero por `UNIDAD`, hasta 3 decimales por `KG` | DEC-79, DEC-98 |
| Al modificar, el cambio se mide contra el stock que mostró el formulario (campo oculto), no contra el actual: una venta hecha mientras se editaba no se deshace | DEC-98 |
| Si cambió: en la misma transacción que el producto, con el producto bloqueado, `mover_stock(producto, nuevo - anterior)` y un `ajuste_stock` con usuario, fecha, anterior, nuevo y motivo. Motivo opcional, por defecto "Modificación manual" | RI-07, RI-17, DEC-96, DEC-98 |
| En el alta, un stock mayor a 0 se registra con motivo "Stock inicial" y anterior 0; la cajera con permiso no tiene el campo y el servicio rechaza su stock | DEC-33, DEC-99 |
| El panel usa el mismo servicio (`save_model`) y valida el stock en el formulario; `ajuste_stock` es de solo lectura | DEC-31, DEC-100 |

**Criterios de aceptación:**
1. Un aceite con stock 10 cambiado a 7 queda en 7 y deja un ajuste 10 → 7 con el motivo elegido o "Modificación manual" (CP-107).
2. Sin cambio no hay ajuste; con una venta hecha mientras se editaba, guardar sin tocar el stock no la deshace (CP-107).
3. -1, 1,5 por unidad o 0,0005 kg se rechazan junto al campo, igual que un cambio en un producto sin control de stock (CP-107).
4. Alta con stock 12: ajuste "Stock inicial" 0 → 12; sin valor, 0 sin ajuste; la cajera con permiso no ve el campo (CP-108).
5. En el panel, el alta y la modificación usan el servicio y registran el ajuste; un stock inválido se marca junto al campo; los ajustes no se crean, modifican ni borran (CP-109).
6. `ajuste_stock` existe con auditoría, sus `CHECK` y su índice (CP-73).

## 2. Comandos

```bash
.venv/bin/python manage.py makemigrations catalogo   # 0005: motivo nuevo, sin observación
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest
```

## 3. Estructura

| Archivo | Cambio |
|---|---|
| `apps/catalogo/models.py` | `MotivoAjuste` con "Modificación manual"; `AjusteStock` sin observación |
| `apps/catalogo/services.py` | `crear_producto(..., stock)`, `modificar_producto(..., stock, stock_mostrado, motivo)`, `stock_cambiado`, `validar_stock_editado` |
| `apps/catalogo/forms.py`, `views.py` | Campos de stock solo para el Administrador (`campos_de_stock`) |
| `apps/catalogo/admin.py` | Formulario con stock editable, motivo y stock mostrado; `save_model` con el servicio; `AjusteStockAdmin` de solo lectura |

## 4. Límites

- **Siempre:** `mover_stock` como única forma de cambiar el stock; el panel nunca guarda el producto directo.
- **Nunca:** editar o borrar ajustes; mostrar el stock a la cajera.
- **Fuera de este spec:** `movimiento_stock` (DEC-24), aviso en la venta (DEC-102, etapa 5).
