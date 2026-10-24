"""Configuración del proyecto. Los valores sensibles salen del entorno (.env, D-14)."""

from pathlib import Path

import environ
from django.templatetags.static import static
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DJANGO_DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
# Contraseña de los usuarios de ejemplo (cargar_datos_ejemplo); solo para desarrollo local.
DEMO_PASSWORD = env("DEMO_PASSWORD", default="")
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    # Tema del panel de administración (DEC-30); va antes de django.contrib.admin.
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.comun",
    "apps.usuarios",
    "apps.caja",
    "apps.ventas",
    "apps.catalogo",
    "apps.proveedores",
    "apps.clientes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.comun.context_processors.menu",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL local (D-04, D-12). pytest-django crea y borra su propia base test_<DB_NAME>.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
    }
}

# Claves primarias de 64 bits (D-05).
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Modelo de usuario propio (DEC-27).
AUTH_USER_MODEL = "usuarios.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Tucuman"
USE_I18N = True
# Traducciones propias de los textos de Unfold que no vienen en español (DEC-30).
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# CU-10 (H1.5): ingreso y salida propios, para todos los roles.
LOGIN_URL = "usuarios:ingresar"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "usuarios:ingresar"
# Cierre de sesión por inactividad: a confirmar (PR-34). Mientras tanto, el valor por defecto
# de Django (la sesión dura dos semanas).


# Panel de administración con Unfold (DEC-30). Rojo de marca (desde 500, un tono más oscuro
# que el rojo de Tailwind para coincidir con el logo del sistema); grises por defecto del tema.
def _item(titulo, icono, url):
    return {"title": titulo, "icon": icono, "link": reverse_lazy(url)}


UNFOLD = {
    "SITE_TITLE": "Carnicería Rojano",
    "SITE_HEADER": "Carnicería Rojano",
    "SITE_SUBHEADER": "Administración",
    "SITE_SYMBOL": "storefront",
    "SITE_URL": "/",
    # Solo modo claro y estilos propios para que el panel se vea como / (DEC-30).
    "THEME": "light",
    "STYLES": [lambda request: static("css/admin.css")],
    "COLORS": {
        "primary": {
            "50": "oklch(97.1% .013 17.38)",
            "100": "oklch(93.6% .032 17.717)",
            "200": "oklch(88.5% .062 18.334)",
            "300": "oklch(80.8% .114 19.571)",
            "400": "oklch(70.4% .191 22.216)",
            "500": "oklch(57.7% .245 27.325)",
            "600": "oklch(50.5% .213 27.518)",
            "700": "oklch(44.4% .177 26.899)",
            "800": "oklch(39.6% .141 25.723)",
            "900": "oklch(25.8% .092 26.042)",
            "950": "oklch(20% .07 26)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "items": [
                    {"title": "Inicio del sistema", "icon": "home", "link": "/", "active": False},
                    _item("Panel", "dashboard", "admin:index"),
                ],
            },
            {
                "title": "Ventas y caja",
                "items": [
                    _item("Ventas", "receipt_long", "admin:ventas_venta_changelist"),
                    _item("Detalle de ventas", "list_alt", "admin:ventas_detalleventa_changelist"),
                    _item("Cajas", "point_of_sale", "admin:caja_caja_changelist"),
                    _item(
                        "Movimientos de caja", "swap_vert", "admin:caja_movimientocaja_changelist"
                    ),
                    _item(
                        "Cierres de caja", "fact_check", "admin:caja_cierrecajadetalle_changelist"
                    ),
                    _item("Medios de pago", "credit_card", "admin:caja_mediopago_changelist"),
                ],
            },
            {
                "title": "Catálogo",
                "items": [
                    _item("Productos", "inventory_2", "admin:catalogo_producto_changelist"),
                    _item("Categorías", "category", "admin:catalogo_categoria_changelist"),
                ],
            },
            {
                "title": "Clientes",
                "items": [
                    _item("Clientes", "groups", "admin:clientes_cliente_changelist"),
                    _item("Pagos de clientes", "payments", "admin:clientes_pagocliente_changelist"),
                    _item(
                        "Cuentas corrientes",
                        "account_balance_wallet",
                        "admin:clientes_movimientocuentacorriente_changelist",
                    ),
                ],
            },
            {
                "title": "Proveedores",
                "items": [
                    _item(
                        "Proveedores", "local_shipping", "admin:proveedores_proveedor_changelist"
                    ),
                    _item(
                        "Ingresos de mercadería",
                        "move_to_inbox",
                        "admin:proveedores_ingresomercaderia_changelist",
                    ),
                    _item(
                        "Detalle de ingresos",
                        "list_alt",
                        "admin:proveedores_detalleingreso_changelist",
                    ),
                    _item(
                        "Precios de proveedores",
                        "sell",
                        "admin:proveedores_productoproveedor_changelist",
                    ),
                    _item(
                        "Pagos a proveedores",
                        "payments",
                        "admin:proveedores_pagoproveedor_changelist",
                    ),
                ],
            },
            {
                "title": "Usuarios",
                "items": [
                    _item("Usuarios", "person", "admin:usuarios_usuario_changelist"),
                    _item("Grupos", "admin_panel_settings", "admin:auth_group_changelist"),
                ],
            },
        ],
    },
}
