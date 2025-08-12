from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from .events.models import DowntimeEvent
from .events.serializers import DowntimeEventSerializer

@receiver(post_save, sender=DowntimeEvent)
def push_event_ws(sender, instance: DowntimeEvent, created, **kwargs):
    if not created:
        return
    layer = get_channel_layer()
    if not layer:
        return
    payload = DowntimeEventSerializer(instance).data
    async_to_sync(layer.group_send)(
        "downtime",
        {"type": "event.push", "event": payload},
    )
