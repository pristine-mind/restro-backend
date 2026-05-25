"""
Django settings for main project.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=str,
    DJANGO_CORS_ORIGIN_REGEX_WHITELIST=(list, []),
    # Database
    DB_NAME=str,
    DB_USER=str,
    DB_PASSWORD=str,
    DB_HOST=str,
    DB_PORT=int,
    # -- For running test (Optional)
    TEST_DJANGO_CACHE_REDIS_URL=(str, None),
    # Static, Media configs
    DJANGO_STATIC_URL=(str, "/static/"),
    DJANGO_MEDIA_URL=(str, "/media/"),
    # -- File System
    DJANGO_STATIC_ROOT=(str, os.path.join(BASE_DIR, "static")),
    DJANGO_MEDIA_ROOT=(str, os.path.join(BASE_DIR, "media")),
    # Testing
    PYTEST_XDIST_WORKER=(str, None),
    # Frontend & Google OAuth2
    FRONTEND_URL=(str, "http://localhost:5173"),
    ALLOWED_REDIRECT_URLS=(list, ["http://localhost:5173"]),
)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DJANGO_DEBUG")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOST")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "main.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            "apps/templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "main.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "OPTIONS": {"options": "-c search_path=public"},
    },
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = env("DJANGO_TIME_ZONE")

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = env("DJANGO_STATIC_URL")
MEDIA_URL = env("DJANGO_MEDIA_URL")

# Default
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

STATIC_ROOT = env("DJANGO_STATIC_ROOT")
MEDIA_ROOT = env("DJANGO_MEDIA_ROOT")

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom User Model
# AUTH_USER_MODEL = "user.User"

# Frontend & Redirect URLs Configuration
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
ALLOWED_REDIRECT_URLS = env.list("ALLOWED_REDIRECT_URLS", default=["http://localhost:3000"])


CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
)

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "sentry-trace",
]

CORS_EXPOSE_HEADERS = [
    "content-type",
    "x-csrftoken",
]


# See if we are inside a test environment (pytest)
TESTING = (
    any(
        [
            arg in sys.argv
            for arg in [
                "test",
                "pytest",
                "/usr/local/bin/pytest",
                "py.test",
                "/usr/local/bin/py.test",
                "/usr/local/lib/python3.12/dist-packages/py/test.py",
            ]
            # Provided by pytest-xdist
        ]
    )
    or env("PYTEST_XDIST_WORKER") is not None
)


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}


TINYMCE_DEFAULT_CONFIG = {
    "entity_encoding": "raw",
    "height": 360,
    "width": 1120,
    "cleanup_on_startup": True,
    "custom_undo_redo_levels": 20,
    "plugins": """
        anchor autolink charmap code codesample directionality
        fullscreen image insertdatetime link lists media
        nonbreaking pagebreak preview save searchreplace table
        visualblocks visualchars
        """,
    "toolbar1": """
        bold italic underline superscript subscript fontsizeselect
        | alignleft alignright | aligncenter alignjustify
        | indent outdent | bullist numlist |
        | link visualchars charmap image hr nonbreaking | code preview fullscreen
        """,
    "paste_data_images": False,
    "force_p_newlines": True,  # TODO: could be False?
    "force_br_newlines": True,  # TODO: could be False?
    "forced_root_block": "",
    "contextmenu": "formats | link",
    "menubar": False,
    "statusbar": False,
    "invalid_styles": {"*": "opacity"},  # Global invalid style
    # https://www.tiny.cloud/docs/configure/content-filtering/#invalid_styles
    # "extended_valid_elements": "iframe[src|frameborder|style|scrolling|class|width|height|name|align]",
    # If more formatting possibilities needed (or more rows), choose from these:
    # "toolbar1": """,
    # fullscreen preview bold italic underline | fontselect,
    # fontsizeselect  | forecolor backcolor | alignleft alignright |
    # aligncenter alignjustify | indent outdent | bullist numlist table |
    # | link image media | codesample |
    # """,
    # "toolbar2": """
    # visualblocks visualchars |
    # charmap hr pagebreak nonbreaking anchor |  code |
    # """,
}
