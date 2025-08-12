from datetime import timedelta
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import DowntimeEvent
from .serializers import DowntimeEventSerializer

@api_view(["GET"])
def recent_events(request):
    minutes = int(request.GET.get("minutes", 60))
    qs = DowntimeEvent.objects.filter(ts__gte=timezone.now()-timedelta(minutes=minutes)).order_by("ts")
    return Response(DowntimeEventSerializer(qs, many=True).data)
