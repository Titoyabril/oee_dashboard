from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # API endpoints
    path('api/', include('oee_analytics.api.urls')),  # Main API (REST + GraphQL)
    path('api/events/', include('oee_analytics.events.urls')),  # Legacy events API

    # Admin
    path('admin/', admin.site.urls),

    # Dashboard views
    path('', include('oee_analytics.urls')),  # Dashboard view
    path('django_plotly_dash/', include('django_plotly_dash.urls')),  # Dash components
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)