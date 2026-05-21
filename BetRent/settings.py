from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# ---------------------------------------------------------------------------
# Application Definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "accounts.apps.AccountsConfig",
    "core.apps.CoreConfig",
    "categories.apps.CategoriesConfig",
    "listings.apps.ListingsConfig",
    "bookings.apps.BookingsConfig",
    "reviews.apps.ReviewsConfig",
    "payments.apps.PaymentsConfig",
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "djoser",
    "axes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "BetRent.urls"
WSGI_APPLICATION = "BetRent.wsgi.application"

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

# ---------------------------------------------------------------------------
# Smart Database Fallback (Postgres -> SQLite)
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres"):
    DATABASES = {
        "default": dj_database_url.config(default=DATABASE_URL)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Cache (Redis via django-redis with Upstash support)
# ---------------------------------------------------------------------------
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
    redis_host = UPSTASH_REDIS_REST_URL.replace("https://", "").replace("http://", "")
    REDIS_URL = f"rediss://default:{UPSTASH_REDIS_REST_TOKEN}@{redis_host}:6379"
else:
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 1,
            "SOCKET_TIMEOUT": 1,
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "betrent",
        "TIMEOUT": 300,
    }
}

# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.BetRentPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BetRent API",
    "DESCRIPTION": "Rent Anything, Anywhere in Ethiopia — BetRent Rental Marketplace API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# Security & Auth
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = DEBUG

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AXES_FAILURE_LIMIT = 5
AXES_USERNAME_FORM_FIELD = "email"
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# ---------------------------------------------------------------------------
# Unfold Admin
# ---------------------------------------------------------------------------
UNFOLD = {
    "SITE_TITLE": "BetRent Admin",
    "SITE_HEADER": "BetRent Marketplace",
    "SITE_SYMBOL": "home_work",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
            "950": "59 7 100",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Accounts & Auth",
                "separator": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "people",
                        "link": "/admin/accounts/user/",
                    },
                    {
                        "title": "Groups",
                        "icon": "group_work",
                        "link": "/admin/auth/group/",
                    },
                ],
            },
            {
                "title": "Marketplace",
                "separator": True,
                "items": [
                    {
                        "title": "Listings",
                        "icon": "home_work",
                        "link": "/admin/listings/listing/",
                    },
                    {
                        "title": "Categories",
                        "icon": "category",
                        "link": "/admin/categories/category/",
                    },
                    {
                        "title": "Listing Images",
                        "icon": "image",
                        "link": "/admin/listings/listingimage/",
                    },
                ],
            },
            {
                "title": "Operations",
                "separator": True,
                "items": [
                    {
                        "title": "Bookings",
                        "icon": "event_available",
                        "link": "/admin/bookings/booking/",
                    },
                    {
                        "title": "Payments",
                        "icon": "payments",
                        "link": "/admin/payments/payment/",
                    },
                    {
                        "title": "Reviews",
                        "icon": "star",
                        "link": "/admin/reviews/review/",
                    },
                ],
            },
            {
                "title": "Security (Axes)",
                "separator": True,
                "items": [
                    {
                        "title": "Access Attempts",
                        "icon": "lock_open",
                        "link": "/admin/axes/accessattempt/",
                    },
                    {
                        "title": "Access Failures",
                        "icon": "lock",
                        "link": "/admin/axes/accessfailurelog/",
                    },
                    {
                        "title": "Access Logs",
                        "icon": "history_edu",
                        "link": "/admin/axes/accesslog/",
                    },
                ],
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Celery Configuration
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# ---------------------------------------------------------------------------
# Chapa Payment Gateway
# ---------------------------------------------------------------------------
CHAPA_SECRET_KEY = os.environ.get("CHAPA_SECRET_KEY", "")
