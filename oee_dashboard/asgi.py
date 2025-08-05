import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import django_plotly_dash.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oee_dashboard.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            django_plotly_dash.routing.websocket_urlpatterns
        )
    ),
})