from django.urls import path
from .views import recent_events

urlpatterns = [
    path("recent/", recent_events),
]
