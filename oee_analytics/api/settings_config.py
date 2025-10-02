"""
Django Settings Configuration for OEE Analytics API

Add these settings to your settings.py file
"""

# Add to INSTALLED_APPS
INSTALLED_APPS_ADDITIONS = [
    'rest_framework',
    'rest_framework.authtoken',
    'graphene_django',
    'django_filters',
    'corsheaders',  # Optional: for CORS support
]

# REST Framework Configuration
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
        'rest_framework.renderers.BrowsableAPIRenderer',  # Disable in production
    ],
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',

    # Throttling (rate limiting)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',  # Anonymous users
        'user': '1000/hour',  # Authenticated users
    },
}

# GraphQL Configuration
GRAPHENE = {
    'SCHEMA': 'oee_analytics.api.schema.schema',
    'MIDDLEWARE': [
        'graphene_django.debug.DjangoDebugMiddleware',
    ],
}

# CORS Configuration (if frontend is on different domain)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React/Vue dev server
    "http://localhost:8080",  # Alternative frontend port
    "https://dashboard.yourcompany.com",  # Production frontend
]

# Or allow all origins (NOT recommended for production)
# CORS_ALLOW_ALL_ORIGINS = True

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

# Add CORS middleware (if using)
# Add to MIDDLEWARE after 'django.middleware.security.SecurityMiddleware'
MIDDLEWARE_ADDITIONS = [
    'corsheaders.middleware.CorsMiddleware',  # Should be as early as possible
]

# Database router for TimescaleDB (if not already configured)
DATABASE_ROUTERS = ['oee_analytics.db.router.TimeSeriesRouter']


# ============================================================================
# Complete Example settings.py snippet
# ============================================================================

EXAMPLE_SETTINGS = """
# In your settings.py, add:

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework.authtoken',
    'graphene_django',
    'django_filters',
    'corsheaders',
    'channels',

    # Your apps
    'oee_analytics',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # Add this
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# REST Framework
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

# GraphQL
GRAPHENE = {
    'SCHEMA': 'oee_analytics.api.schema.schema',
}

# CORS (adjust for your frontend)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]

# Database Routing
DATABASE_ROUTERS = ['oee_analytics.db.router.TimeSeriesRouter']
"""


def print_setup_instructions():
    """Print setup instructions"""
    print("""
================================================================================
OEE Analytics API - Setup Instructions
================================================================================

1. Install required packages:

   pip install djangorestframework django-filter graphene-django django-cors-headers

2. Add apps to INSTALLED_APPS in settings.py:

   'rest_framework',
   'rest_framework.authtoken',
   'graphene_django',
   'django_filters',
   'corsheaders',

3. Add middleware (after SecurityMiddleware):

   'corsheaders.middleware.CorsMiddleware',

4. Add REST_FRAMEWORK and GRAPHENE settings (see EXAMPLE_SETTINGS above)

5. Run migrations:

   python manage.py migrate

6. Create auth tokens for users:

   python manage.py drf_create_token <username>

   Or create token in code:

   from rest_framework.authtoken.models import Token
   token = Token.objects.create(user=user)
   print(token.key)

7. Test endpoints:

   # Get token
   curl -X POST http://localhost:8000/api/auth/token/ \\
     -H "Content-Type: application/json" \\
     -d '{"username":"admin","password":"password"}'

   # Test API
   curl http://localhost:8000/api/machines/ \\
     -H "Authorization: Token YOUR_TOKEN_HERE"

   # Test GraphQL
   Visit: http://localhost:8000/api/graphql/

================================================================================
    """)


if __name__ == "__main__":
    print_setup_instructions()
