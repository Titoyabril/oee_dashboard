from django.urls import re_path
from .consumer import EventsConsumer

websocket_urlpatterns = [
    re_path(r"^ws/events/$", EventsConsumer.as_asgi()),
]
