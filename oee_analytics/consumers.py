"""
WebSocket Consumers for Real-Time Dashboard Updates
Provides live streaming of PLC data, OEE metrics, machine status, and events
"""
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class DashboardConsumer(AsyncJsonWebsocketConsumer):
    """
    Main dashboard consumer for real-time OEE metrics and machine status
    Subscribes to: metrics, machine_status, events, alerts
    """

    async def connect(self):
        # Extract query parameters for filtering
        self.line_id = self.scope['url_route']['kwargs'].get('line_id', 'all')
        self.machine_id = self.scope['url_route']['kwargs'].get('machine_id', None)

        # Join appropriate groups based on filters
        if self.machine_id:
            await self.channel_layer.group_add(f"machine_{self.machine_id}", self.channel_name)
        elif self.line_id and self.line_id != 'all':
            await self.channel_layer.group_add(f"line_{self.line_id}", self.channel_name)

        # Always join global channels
        await self.channel_layer.group_add("metrics", self.channel_name)
        await self.channel_layer.group_add("machine_status", self.channel_name)
        await self.channel_layer.group_add("alerts", self.channel_name)

        await self.accept()

        # Send initial data snapshot
        await self.send_initial_snapshot()

    async def disconnect(self, code):
        # Leave all groups
        if self.machine_id:
            await self.channel_layer.group_discard(f"machine_{self.machine_id}", self.channel_name)
        elif self.line_id and self.line_id != 'all':
            await self.channel_layer.group_discard(f"line_{self.line_id}", self.channel_name)

        await self.channel_layer.group_discard("metrics", self.channel_name)
        await self.channel_layer.group_discard("machine_status", self.channel_name)
        await self.channel_layer.group_discard("alerts", self.channel_name)

    async def send_initial_snapshot(self):
        """Send initial data snapshot on connection"""
        try:
            snapshot = await self.get_initial_data()
            await self.send_json({
                'type': 'snapshot',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'data': snapshot
            })
        except Exception as e:
            await self.send_json({
                'type': 'error',
                'message': f'Failed to load initial snapshot: {str(e)}'
            })

    @database_sync_to_async
    def get_initial_data(self) -> Dict[str, Any]:
        """Get initial data snapshot from database"""
        from oee_analytics.models.asset_hierarchy import Machine

        # Get machines based on filter
        if self.machine_id:
            machines = Machine.objects.filter(machine_id=self.machine_id, active=True)
        elif self.line_id and self.line_id != 'all':
            machines = Machine.objects.filter(cell__line__line_id=self.line_id, active=True)
        else:
            machines = Machine.objects.filter(active=True)[:20]  # Limit to 20 machines

        return {
            'machines': [{
                'machine_id': m.machine_id,
                'name': m.name,
                'status': m.status,
                'oee': float(m.current_oee_percent) if m.current_oee_percent else None,
                'availability': float(m.current_availability_percent) if m.current_availability_percent else None,
                'performance': float(m.current_performance_percent) if m.current_performance_percent else None,
                'quality': float(m.current_quality_percent) if m.current_quality_percent else None,
                'line': m.cell.line.name if m.cell and m.cell.line else None,
            } for m in machines]
        }

    # Handlers for incoming messages from backend
    async def metrics_update(self, event):
        """Handle OEE metrics updates"""
        await self.send_json({
            'type': 'metrics',
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'data': event['data']
        })

    async def machine_status_update(self, event):
        """Handle machine status changes"""
        await self.send_json({
            'type': 'machine_status',
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'data': event['data']
        })

    async def alert_message(self, event):
        """Handle alerts"""
        await self.send_json({
            'type': 'alert',
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'data': event['data']
        })


class PLCDataConsumer(AsyncJsonWebsocketConsumer):
    """
    Real-time PLC data streaming consumer
    Subscribes to live PLC tag updates from specific machines
    """

    async def connect(self):
        # Get machine IDs from query parameter or URL
        self.machine_ids = self.scope['url_route']['kwargs'].get('machine_ids', '').split(',')

        # Join groups for each machine
        for machine_id in self.machine_ids:
            if machine_id:
                await self.channel_layer.group_add(f"plc_data_{machine_id}", self.channel_name)

        await self.accept()

        await self.send_json({
            'type': 'connected',
            'message': f'Subscribed to PLC data for machines: {", ".join(self.machine_ids)}'
        })

    async def disconnect(self, code):
        # Leave all machine groups
        for machine_id in self.machine_ids:
            if machine_id:
                await self.channel_layer.group_discard(f"plc_data_{machine_id}", self.channel_name)

    async def plc_data_update(self, event):
        """Handle real-time PLC tag updates"""
        await self.send_json({
            'type': 'plc_data',
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'machine_id': event.get('machine_id'),
            'data': event['data']
        })


class EventsConsumer(AsyncJsonWebsocketConsumer):
    """
    Event stream consumer for production events, faults, and downtime
    """

    async def connect(self):
        # Join multiple groups for different types of updates
        await self.channel_layer.group_add("events", self.channel_name)
        await self.channel_layer.group_add("metrics", self.channel_name)
        await self.channel_layer.group_add("alerts", self.channel_name)
        await self.channel_layer.group_add("downtime", self.channel_name)
        await self.channel_layer.group_add("dataflow", self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        # Leave all groups
        await self.channel_layer.group_discard("events", self.channel_name)
        await self.channel_layer.group_discard("metrics", self.channel_name)
        await self.channel_layer.group_discard("alerts", self.channel_name)
        await self.channel_layer.group_discard("downtime", self.channel_name)
        await self.channel_layer.group_discard("dataflow", self.channel_name)

    # Handle different message types from backend
    async def event_message(self, event):
        """Handle machine events"""
        await self.send_json({
            'type': 'event',
            'data': event['message']
        })

    async def metrics_update(self, event):
        """Handle OEE metrics updates"""
        await self.send_json({
            'type': 'metrics',
            'data': event['metrics']
        })

    async def alert_message(self, event):
        """Handle alerts"""
        await self.send_json({
            'type': 'alert',
            'data': event['alert']
        })

    async def dataflow_update(self, event):
        """Handle data flow monitoring updates"""
        await self.send_json({
            'type': 'dataflow',
            'data': event['dataflow']
        })

    # Legacy handler for backwards compatibility
    async def event_push(self, event):
        """Legacy event handler"""
        await self.send_json(event["event"])


class MachineConfigurationConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer for machine configuration changes and connection status updates
    Used during machine setup and testing
    """

    async def connect(self):
        await self.channel_layer.group_add("machine_config", self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard("machine_config", self.channel_name)

    async def config_update(self, event):
        """Handle configuration changes"""
        await self.send_json({
            'type': 'config_update',
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'data': event['data']
        })

    async def connection_test_result(self, event):
        """Handle connection test results"""
        await self.send_json({
            'type': 'test_result',
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'data': event['data']
        })

    async def tag_discovery_progress(self, event):
        """Handle tag discovery progress updates"""
        await self.send_json({
            'type': 'discovery_progress',
            'timestamp': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'data': event['data']
        })
