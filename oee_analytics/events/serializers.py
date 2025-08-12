from rest_framework import serializers
from .models import DowntimeEvent

class DowntimeEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DowntimeEvent
        fields = "__all__"
