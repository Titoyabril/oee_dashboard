from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-not-for-prod")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in {"1","true","yes"}
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Dash + Channels + API
    "django_plotly_dash",
    #"dpd_static_support",
    "channels",
    "rest_framework",
    "rest_framework.authtoken",
    "graphene_django",
    "django_filters",
    "corsheaders",

    "oee_analytics",
]

MIDDLEWARE = [
    "django_plotly_dash.middleware.BaseMiddleware",
    "django_plotly_dash.middleware.ExternalRedirectionMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "oee_dashboard.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]

WSGI_APPLICATION = "oee_dashboard.wsgi.application"
ASGI_APPLICATION = "oee_dashboard.asgi.application"

# Database configuration
# Use TimescaleDB for time-series data, SQLite/SQL Server for config data
USE_SQL_SERVER = os.getenv("USE_SQL_SERVER", "False").lower() in {"1","true","yes"}
USE_TIMESCALEDB = os.getenv("USE_TIMESCALEDB", "True").lower() in {"1","true","yes"}

if USE_SQL_SERVER:
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.getenv("SQL_SERVER_DB", "oee_analytics"),
            "USER": os.getenv("SQL_SERVER_USER", "sa"),
            "PASSWORD": os.getenv("SQL_SERVER_PASSWORD", "OEE_Analytics2024!"),
            "HOST": os.getenv("SQL_SERVER_HOST", "localhost"),
            "PORT": os.getenv("SQL_SERVER_PORT", "1433"),
            "OPTIONS": {
                "driver": "ODBC Driver 17 for SQL Server",
                "extra_params": "TrustServerCertificate=yes"
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Add TimescaleDB for time-series data
if USE_TIMESCALEDB:
    DATABASES["timescaledb"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("TIMESCALE_DB", "oee_analytics"),
        "USER": os.getenv("TIMESCALE_USER", "oeeuser"),
        "PASSWORD": os.getenv("TIMESCALE_PASSWORD", "OEE_Analytics2024!"),
        "HOST": os.getenv("TIMESCALE_HOST", "localhost"),
        "PORT": os.getenv("TIMESCALE_PORT", "5432"),
        "OPTIONS": {
            "options": "-c search_path=public",
            "connect_timeout": 10,
        },
        "CONN_MAX_AGE": 600,  # Persistent connections for 10 minutes
        "ATOMIC_REQUESTS": False,  # Better performance for bulk inserts
    }

# Database router for time-series data
DATABASE_ROUTERS = [
    'oee_analytics.db.router.TimeSeriesRouter',
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---- Channels / Redis with safe fallback ----
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
USE_IN_MEMORY_CHANNELS = os.getenv("USE_IN_MEMORY_CHANNELS", "").lower() in {"1","true","yes"}

if USE_IN_MEMORY_CHANNELS:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }

# ---- Static files ----
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "django_plotly_dash.finders.DashAssetFinder",
    "django_plotly_dash.finders.DashComponentFinder",
    "django_plotly_dash.finders.DashAppDirectoryFinder",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Allow Dash iframes
X_FRAME_OPTIONS = "SAMEORIGIN"

# ---- REST Framework Configuration ----
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# ---- GraphQL Configuration ----
GRAPHENE = {
    'SCHEMA': 'oee_analytics.api.schema.schema',
    'MIDDLEWARE': [
        'graphene_django.debug.DjangoDebugMiddleware',
    ],
}

# ---- CORS Configuration ----
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ---- Celery Configuration ----
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Celery beat schedule for periodic tasks
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'calculate-oee-metrics': {
        'task': 'oee_analytics.tasks.calculate_oee_metrics',
        'schedule': 30.0,  # Every 30 seconds
    },
    'cleanup-old-events': {
        'task': 'oee_analytics.tasks.cleanup_old_events',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    # ML Pipeline Tasks (Phase 2)
    'extract-ml-features': {
        'task': 'oee_analytics.tasks.extract_ml_features',
        'schedule': 60.0,  # Every 60 seconds
    },
    'run-downtime-prediction': {
        'task': 'oee_analytics.tasks.run_downtime_prediction',
        'schedule': 120.0,  # Every 2 minutes
    },
    'calculate-oee-forecast': {
        'task': 'oee_analytics.tasks.calculate_oee_forecast',
        'schedule': 300.0,  # Every 5 minutes
    },
    'quality-risk-scoring': {
        'task': 'oee_analytics.tasks.quality_risk_scoring',
        'schedule': 90.0,  # Every 90 seconds
    },
}
