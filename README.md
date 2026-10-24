# Sistema de gestión - Carnicería Rojano

Sistema web de caja, ventas, stock, proveedores y cuentas corrientes para Carnicería Rojano
(Trabajo de Campo). La documentación del proyecto, fuente de verdad del diseño, está en [`docs/`](docs/).

Stack: Python 3.13, Django 5.2 LTS, PostgreSQL 18, Tailwind CSS (ver [06-arquitectura.md](docs/06-arquitectura.md)).

## Instalación local

Los pasos usan macOS con [Homebrew](https://brew.sh); en otro sistema, instalar Python 3.13 y PostgreSQL 18
con el método habitual y seguir desde el paso 3.

### 1. Python 3.13 y entorno virtual

```bash
brew install python@3.13
```

Desde la raíz del repositorio:

```bash
python3.13 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

Todos los comandos siguientes se corren con el entorno virtual activado.

### 2. PostgreSQL

```bash
brew install postgresql@18
```

```bash
brew services start postgresql@18
```

### 3. Base y usuario de desarrollo

Crear un usuario exclusivo de desarrollo con permiso para crear bases (las pruebas crean y borran su
propia base `test_carniceria_dev`) y la base de desarrollo. Elegir una contraseña local, que solo va en el `.env`:

```bash
createuser --createdb --pwprompt carniceria_dev
```

```bash
createdb --owner=carniceria_dev carniceria_dev
```

### 4. Variables de entorno

```bash
cp .env.example .env
```

Completar en `.env` la `DJANGO_SECRET_KEY` (cualquier texto largo local), la `DB_PASSWORD` elegida en el paso 3
y la `DEMO_PASSWORD` de los usuarios de ejemplo (paso 6).
El `.env` no se sube al repositorio. No usar datos ni credenciales reales del negocio.

### 5. Migrar la base

```bash
python manage.py migrate
```

### 6. Datos de ejemplo

Carga datos ficticios para probar el sistema en local: usuarios, medios de pago, categorías,
productos, clientes y proveedores. Se puede correr varias veces: no duplica nada. Solo funciona
con `DJANGO_DEBUG=True`.

La contraseña de los usuarios de ejemplo se define en la variable `DEMO_PASSWORD` del `.env`
(elegir una local; solo para la base de desarrollo, nunca usarla en otro lado). El comando no
corre si falta.

```bash
python manage.py cargar_datos_ejemplo
```

Los usuarios de ejemplo entran en <http://localhost:8000/ingresar/> con esa contraseña:

| Usuario | Rol | Qué ve |
|---|---|---|
| `admin` | Administrador | Todas sus funciones y el panel de administración |
| `cajera_alta` | Cajera con permiso de alta de productos | Ventas, caja y productos |
| `cajera` | Cajera sin ese permiso | Ventas y caja |
| `duenio` | Dueño | Reportes (solo consulta) |

### 7. Usuario administrador

```bash
python manage.py createsuperuser
```

Opcional si ya se cargó el usuario `admin` de los datos de ejemplo. Pide nombre de usuario, nombre completo, rol y contraseña. Como rol, escribir `ADMINISTRADOR`
(los valores válidos son `ADMINISTRADOR`, `CAJERA` y `DUENIO`); solo el Administrador puede acceder al panel, DEC-32). Con ese usuario se entra al panel
de administración en <http://localhost:8000/admin/> después de levantar el servidor:

```bash
python manage.py runserver
```

### 8. Estilos (Tailwind)

Requiere Node.js. Se usa `npm` solo para compilar los estilos (D-13):

```bash
npm install
```

```bash
npm run estilos
```

Durante el desarrollo, `npm run estilos:vigilar` recompila al guardar cambios en las plantillas.

Las traducciones de los textos del panel de administración están en `locale/es`. Si se edita el `.po`,
recompilarlo con `python manage.py compilemessages` (requiere `gettext`: `brew install gettext`).
La pantalla de inicio queda en <http://localhost:8000/>.

### 9. Pruebas y formato

```bash
pytest
```

```bash
ruff check .
```

```bash
ruff format --check .
```

`pytest` usa una base de prueba separada; nunca toca la base de desarrollo. Antes de cada commit,
`ruff format .` deja el código con el formato del proyecto.

## Estructura

```
config/   configuración del proyecto
apps/     un módulo por área: usuarios, caja, ventas, catalogo, proveedores, clientes
          (comun guarda el modelo base de auditoría)
docs/     documentación
```

Cada módulo separa las capas: `models.py` (datos), `services.py` (reglas de negocio), `views.py` y
`forms.py` (pantallas), con sus pruebas en `tests/`.
