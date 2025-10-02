"""
Edge Gateway with Adaptive Sampling
Integrates OPC-UA clients with Sparkplug publisher and implements
adaptive sampling based on MQTT backpressure
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from .mqtt_client import SparkplugMQTTClient, SparkplugConfig
from .connectors.opcua_client import OPCUAClient, OPCUAConfig, MonitoredItemConfig
from .connectors.base import PLCDataPoint


@dataclass
class AdaptiveSamplingConfig:
    """Configuration for adaptive sampling behavior"""
    normal_sampling_ms: int = 250      # Normal sampling interval
    backpressure_sampling_ms: int = 2000  # Sampling interval under backpressure
    transition_delay_s: float = 5.0    # Delay before applying sampling changes


class EdgeGateway:
    """
    Edge Gateway that coordinates OPC-UA clients and Sparkplug publisher
    Implements adaptive sampling to handle backpressure
    """

    def __init__(
        self,
        sparkplug_config: SparkplugConfig,
        opcua_configs: List[OPCUAConfig],
        adaptive_config: Optional[AdaptiveSamplingConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.adaptive_config = adaptive_config or AdaptiveSamplingConfig()

        # Initialize Sparkplug MQTT client
        self.sparkplug_client = SparkplugMQTTClient(sparkplug_config, logger)

        # Initialize OPC-UA clients
        self.opcua_clients: List[OPCUAClient] = []
        for config in opcua_configs:
            client = OPCUAClient(config)
            client.data_callback = self._handle_opcua_data
            self.opcua_clients.append(client)

        # Adaptive sampling state
        self.current_sampling_mode = 'normal'
        self.monitored_items: Dict[OPCUAClient, List[MonitoredItemConfig]] = {}

        # Statistics
        self.stats = {
            'data_points_received': 0,
            'data_points_published': 0,
            'sampling_changes': 0,
            'backpressure_activations': 0,
        }

        # Register backpressure callback
        self.sparkplug_client.register_backpressure_callback(self._handle_backpressure)

    async def start(self) -> bool:
        """Start the edge gateway"""
        try:
            self.logger.info("Starting Edge Gateway")

            # Start Sparkplug MQTT client
            if not await self.sparkplug_client.start():
                self.logger.error("Failed to start Sparkplug client")
                return False

            # Connect all OPC-UA clients
            success_count = 0
            for i, client in enumerate(self.opcua_clients):
                try:
                    if await client.connect():
                        self.logger.info(f"OPC-UA client {i+1} connected")
                        success_count += 1
                    else:
                        self.logger.error(f"OPC-UA client {i+1} failed to connect")
                except Exception as e:
                    self.logger.error(f"OPC-UA client {i+1} connection error: {e}")

            if success_count == 0:
                self.logger.error("No OPC-UA clients connected")
                return False

            self.logger.info(f"Edge Gateway started ({success_count}/{len(self.opcua_clients)} clients connected)")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start Edge Gateway: {e}")
            return False

    async def stop(self):
        """Stop the edge gateway"""
        try:
            self.logger.info("Stopping Edge Gateway")

            # Disconnect OPC-UA clients
            for client in self.opcua_clients:
                try:
                    await client.disconnect()
                except Exception as e:
                    self.logger.error(f"Error disconnecting OPC-UA client: {e}")

            # Stop Sparkplug client
            await self.sparkplug_client.stop()

            self.logger.info("Edge Gateway stopped")

        except Exception as e:
            self.logger.error(f"Error stopping Edge Gateway: {e}")

    async def add_monitored_items(
        self,
        client: OPCUAClient,
        items: List[MonitoredItemConfig]
    ) -> bool:
        """Add monitored items to an OPC-UA client"""
        try:
            # Store items for later adaptive sampling adjustments
            if client not in self.monitored_items:
                self.monitored_items[client] = []

            for item in items:
                # Apply current sampling mode
                if self.current_sampling_mode == 'backpressure':
                    item.sampling_interval = self.adaptive_config.backpressure_sampling_ms
                else:
                    item.sampling_interval = self.adaptive_config.normal_sampling_ms

                # Add to client
                if await client.add_monitored_item(item):
                    self.monitored_items[client].append(item)
                else:
                    self.logger.error(f"Failed to add monitored item: {item.node_id}")

            return True

        except Exception as e:
            self.logger.error(f"Error adding monitored items: {e}")
            return False

    async def _handle_opcua_data(self, data_point: PLCDataPoint):
        """Handle data received from OPC-UA client"""
        try:
            self.stats['data_points_received'] += 1

            # Convert to Sparkplug metric
            # This is a simplified conversion - in production you'd use proper metric mapping
            metric_name = data_point.tag_name
            metric_value = data_point.value
            timestamp = int(data_point.timestamp.timestamp() * 1000)  # Convert to ms

            # Publish to Sparkplug
            # Note: This would need integration with actual Sparkplug message builder
            # For now, we just log
            self.logger.debug(f"Data point: {metric_name} = {metric_value} @ {timestamp}")
            self.stats['data_points_published'] += 1

            # TODO: Implement actual Sparkplug NDATA/DDATA message publishing
            # This requires integration with SparkplugMessageBuilder

        except Exception as e:
            self.logger.error(f"Error handling OPC-UA data: {e}")

    async def _handle_backpressure(self, active: bool):
        """Handle backpressure events from Sparkplug client"""
        try:
            if active:
                self.logger.warning("Backpressure detected - switching to slow sampling mode")
                self.stats['backpressure_activations'] += 1
                await self._apply_adaptive_sampling('backpressure')
            else:
                self.logger.info("Backpressure cleared - returning to normal sampling mode")
                await self._apply_adaptive_sampling('normal')

        except Exception as e:
            self.logger.error(f"Error handling backpressure: {e}")

    async def _apply_adaptive_sampling(self, mode: str):
        """Apply adaptive sampling changes to all monitored items"""
        if mode == self.current_sampling_mode:
            return

        try:
            self.logger.info(f"Changing sampling mode: {self.current_sampling_mode} -> {mode}")

            # Wait for transition delay
            await asyncio.sleep(self.adaptive_config.transition_delay_s)

            # Determine new sampling interval
            if mode == 'backpressure':
                new_interval = self.adaptive_config.backpressure_sampling_ms
            else:
                new_interval = self.adaptive_config.normal_sampling_ms

            # Update all monitored items
            for client, items in self.monitored_items.items():
                for item in items:
                    old_interval = item.sampling_interval
                    item.sampling_interval = new_interval

                    # Remove and re-add monitored item with new interval
                    try:
                        await client.remove_monitored_item(item.node_id)
                        await client.add_monitored_item(item)
                        self.logger.debug(
                            f"Updated {item.node_id}: {old_interval}ms -> {new_interval}ms"
                        )
                    except Exception as e:
                        self.logger.error(f"Failed to update monitored item {item.node_id}: {e}")

            self.current_sampling_mode = mode
            self.stats['sampling_changes'] += 1

            self.logger.info(f"Sampling mode changed to {mode} ({new_interval}ms)")

        except Exception as e:
            self.logger.error(f"Error applying adaptive sampling: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get gateway statistics"""
        stats = {
            **self.stats,
            'current_sampling_mode': self.current_sampling_mode,
            'opcua_clients': len(self.opcua_clients),
            'monitored_items': sum(len(items) for items in self.monitored_items.values()),
        }

        # Add Sparkplug client stats
        stats['sparkplug'] = self.sparkplug_client.get_statistics()

        # Add OPC-UA client stats
        stats['opcua_connections'] = []
        for i, client in enumerate(self.opcua_clients):
            stats['opcua_connections'].append({
                'index': i,
                'status': client.status.value if hasattr(client, 'status') else 'unknown',
                'endpoint': client.config.endpoint_url if hasattr(client, 'config') else 'unknown',
            })

        return stats


# Example usage
async def main():
    """Example usage of Edge Gateway"""
    # Configure Sparkplug
    sparkplug_config = SparkplugConfig(
        broker_host="localhost",
        broker_port=1883,
        group_id="EdgeGroup",
        node_id="EdgeNode01",
        enable_store_forward=True,
        enable_backpressure=True,
    )

    # Configure OPC-UA servers
    opcua_configs = [
        OPCUAConfig(
            host="192.168.1.10",
            port=4840,
            endpoint_url="opc.tcp://192.168.1.10:4840",
            default_sampling_interval=250,
        ),
    ]

    # Configure adaptive sampling
    adaptive_config = AdaptiveSamplingConfig(
        normal_sampling_ms=250,
        backpressure_sampling_ms=2000,
        transition_delay_s=5.0,
    )

    # Create gateway
    gateway = EdgeGateway(
        sparkplug_config=sparkplug_config,
        opcua_configs=opcua_configs,
        adaptive_config=adaptive_config,
    )

    try:
        # Start gateway
        if await gateway.start():
            print("Gateway started successfully")

            # Add some monitored items
            if gateway.opcua_clients:
                client = gateway.opcua_clients[0]
                items = [
                    MonitoredItemConfig(
                        node_id="ns=2;i=1001",
                        display_name="Temperature",
                        sampling_interval=250,
                        deadband_value=0.5,
                    ),
                    MonitoredItemConfig(
                        node_id="ns=2;i=1002",
                        display_name="Pressure",
                        sampling_interval=250,
                        deadband_value=0.1,
                    ),
                ]
                await gateway.add_monitored_items(client, items)

            # Run for some time
            await asyncio.sleep(300)  # 5 minutes

            # Print statistics
            stats = gateway.get_statistics()
            print(f"Gateway statistics: {stats}")

    finally:
        await gateway.stop()


if __name__ == "__main__":
    asyncio.run(main())
