"""
Django settings for mbg_backend project.
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = [
    "smartsales.co.ke",
    "www.smartsales.co.ke",
    "api.smartsales.co.ke",  # Add this
    "localhost",
    "127.0.0.1"
]
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',   # ✅ only once
    'allauth',
    'allauth.account',
    'allauth.socialaccount',      # optional
    'dj_rest_auth',
    'dj_rest_auth.registration',  # for registration endpoints
    'rest_framework_simplejwt',
    'corsheaders',

    # Your apps
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must come before CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
      "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mbg_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "mbg_backend.wsgi.application"

# DATABASE (SQLite)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}

# PASSWORD VALIDATION
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# INTERNATIONALIZATION
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# STATIC & MEDIA FILES
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS & CSRF SETTINGS
CORS_ALLOWED_ORIGINS = [
    "https://smartsales.co.ke",
    "https://api.smartsales.co.ke",  # add subdomain
    "http://localhost:8080",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "https://smartsales.co.ke",
    "https://api.smartsales.co.ke",  # add subdomain
    "http://localhost:8080",
    "http://127.0.0.1:3000",
]


# JAZZMIN CONFIG
JAZZMIN_SETTINGS = {
    "site_title": "MBG Admin",
    "site_header": "Mastering Business Growth",
    "site_brand": "MBG Admin Portal",
    "welcome_sign": "Welcome to MBG Admin Dashboard",
    "copyright": "© 2025 Mastering Business Growth",
    "topmenu_links": [
        {"name": "Home", "url": "/", "permissions": ["auth.view_user"]},
        {"app": "api"},
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "api.TeamMember": "fas fa-user-tie",
        "api.Program": "fas fa-chalkboard-teacher",
        "api.Event": "fas fa-calendar-check",
    },
}

# JWT SETTINGS
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# EMAIL SETTINGS
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 465))
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

ADMIN_EMAILS = [
    os.getenv("ADMIN_EMAIL_1"),
    os.getenv("ADMIN_EMAIL_2")
]
# settings.py
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:8080')

# Add to your settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'mbg_backend': {  # Replace with your actual app name
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# PesaPal Configuration
PESAPAL_CONFIG = {
    'CONSUMER_KEY': os.getenv('PESAPAL_CONSUMER_KEY', ''),
    'CONSUMER_SECRET': os.getenv('PESAPAL_CONSUMER_SECRET', ''),
    # Use sandbox for testing, live for production
    'BASE_URL': os.getenv('PESAPAL_BASE_URL', 'https://cybqa.pesapal.com/pesapalv3'),  # Sandbox
    # 'BASE_URL': 'https://pay.pesapal.com/v3',  # Production
    'CALLBACK_URL': os.getenv('PESAPAL_CALLBACK_URL', 'http://127.0.0.1:8000/api/payments/pesapal-callback/'),
    'IPN_URL': os.getenv('PESAPAL_IPN_URL', 'http://127.0.0.1:8000/api/payments/pesapal-ipn/'),
}

# Environment variables for security
PESAPAL_CONSUMER_KEY = os.getenv('PESAPAL_CONSUMER_KEY')
PESAPAL_CONSUMER_SECRET = os.getenv('PESAPAL_CONSUMER_SECRET')