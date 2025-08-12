from channels.generic.websocket import AsyncJsonWebsocketConsumer

class EventsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Join multiple groups for different types of updates
        await self.channel_layer.group_add("events", self.channel_name)
        await self.channel_layer.group_add("metrics", self.channel_name)
        await self.channel_layer.group_add("alerts", self.channel_name)
        await self.channel_layer.group_add("downtime", self.channel_name)  # Legacy compatibility
        await self.accept()

    async def disconnect(self, code):
        # Leave all groups
        await self.channel_layer.group_discard("events", self.channel_name)
        await self.channel_layer.group_discard("metrics", self.channel_name)
        await self.channel_layer.group_discard("alerts", self.channel_name)
        await self.channel_layer.group_discard("downtime", self.channel_name)

    # Handle different message types from Celery tasks
    async def event_message(self, event):
        """Handle machine events from Celery"""
        await self.send_json({
            'type': 'event',
            'data': event['message']
        })

    async def metrics_update(self, event):
        """Handle OEE metrics updates from Celery"""
        await self.send_json({
            'type': 'metrics',
            'data': event['metrics']
        })

    async def alert_message(self, event):
        """Handle alerts from Celery"""
        await self.send_json({
            'type': 'alert',
            'data': event['alert']
        })
        
    # Legacy handler for backwards compatibility
    async def event_push(self, event):
        """Legacy event handler"""
        await self.send_json(event["event"])
