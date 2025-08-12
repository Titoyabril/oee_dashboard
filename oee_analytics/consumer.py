from channels.generic.websocket import AsyncJsonWebsocketConsumer

class EventsConsumer(AsyncJsonWebsocketConsumer):
    group_name = "downtime"

    async def connect(self):
        # Join the downtime group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        # Leave the downtime group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def event_push(self, event):
        # Send event data to WebSocket
        await self.send_json(event["event"])
