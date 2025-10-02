"""
Django management command for running OPC-UA agent
Connects to OPC-UA servers and publishes data via Sparkplug B
"""

import asyncio
import signal
import sys
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection
from django.utils import timezone as django_timezone

from prometheus_client import start_http_server

# Import our modules
from oee_analytics.sparkplug.connectors.opcua_client import (
    OPCUAClient, OPCUAConfig, MonitoredItemConfig
)
from oee_analytics.sparkplug.connectors.opcua_config import (
    OPCUAConfigManager, CertificateManager
)
from oee_analytics.sparkplug.mqtt_client import SparkplugMQTTClient, SparkplugConfig
from oee_analytics.sparkplug.data_processor import DataProcessor, OEEMetricType
from oee_analytics.sparkplug.models import (
    OPCUAServerConnection, OPCUANodeMapping, OPCUASubscription,
    SparkplugNode, SparkplugDevice, SparkplugMetric
)

logger = logging.getLogger('opcua_agent')


class OPCUAToSparkplugBridge:
    """Bridges OPC-UA data to Sparkplug B MQTT"""

    def __init__(self, config_manager: OPCUAConfigManager,
                 sparkplug_client: SparkplugMQTTClient,
                 data_processor: DataProcessor):
        self.config_manager = config_manager
        self.sparkplug_client = sparkplug_client
        self.data_processor = data_processor
        self.opcua_clients: Dict[str, OPCUAClient] = {}
        self.running = False
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        """Start the bridge"""
        self.running = True
        logger.info("Starting OPC-UA to Sparkplug B bridge")

        # Connect to MQTT broker
        await self.sparkplug_client.connect()

        # Start OPC-UA clients
        for server_id, server_config in self.config_manager.servers.items():
            if server_config.enabled:
                await self.start_opcua_client(server_id, server_config)

    async def start_opcua_client(self, server_id: str, server_config):
        """Start a single OPC-UA client"""
        try:
            logger.info(f"Starting OPC-UA client for {server_id}")

            # Create OPC-UA config
            opcua_config = OPCUAConfig(
                host=server_config.endpoint_url.split('//')[1].split(':')[0],
                port=int(server_config.endpoint_url.split(':')[-1].split('/')[0]),
                endpoint_url=server_config.endpoint_url,
                security_mode=server_config.security_mode,
                security_policy=server_config.security_policy,
                auth_mode=server_config.auth_mode,
                username=server_config.username,
                password=server_config.password,
                client_cert_path=server_config.client_cert_path,
                client_key_path=server_config.client_key_path,
                server_cert_path=server_config.server_cert_path,
                session_timeout=server_config.session_timeout_ms,
                keep_alive_interval=server_config.keep_alive_interval_ms,
                reconnect_interval=server_config.reconnect_interval_s,
                max_reconnect_attempts=server_config.max_reconnect_attempts,
                publishing_interval=server_config.publishing_interval_ms,
                max_notifications_per_publish=server_config.max_notifications_per_publish,
                max_concurrent_reads=server_config.max_concurrent_reads,
                batch_read_size=server_config.batch_read_size
            )

            # Create client
            client = OPCUAClient(opcua_config)
            client.data_callback = lambda data: self.handle_opcua_data(server_id, data)

            # Connect
            if await client.connect():
                self.opcua_clients[server_id] = client

                # Update database status
                await self.update_server_status(server_id, 'CONNECTED')

                # Add monitored items
                await self.setup_monitored_items(server_id, client, server_config.tags)

                logger.info(f"Successfully connected to {server_id}")
            else:
                logger.error(f"Failed to connect to {server_id}")
                await self.update_server_status(server_id, 'ERROR')

        except Exception as e:
            logger.error(f"Error starting OPC-UA client {server_id}: {e}")
            await self.update_server_status(server_id, 'ERROR', str(e))

    async def setup_monitored_items(self, server_id: str, client: OPCUAClient, tags):
        """Setup monitored items for a client"""
        for tag in tags:
            try:
                config = MonitoredItemConfig(
                    node_id=tag.opcua_node_id,
                    display_name=tag.display_name,
                    sampling_interval=tag.sampling_interval_ms,
                    queue_size=10,
                    deadband_type=tag.deadband_type,
                    deadband_value=tag.deadband_value
                )

                if await client.add_monitored_item(config):
                    logger.info(f"Added monitored item: {tag.display_name}")
                else:
                    logger.error(f"Failed to add monitored item: {tag.display_name}")

            except Exception as e:
                logger.error(f"Error adding monitored item {tag.display_name}: {e}")

    async def handle_opcua_data(self, server_id: str, data_point):
        """Handle data from OPC-UA and publish to Sparkplug"""
        try:
            # Get tag mapping
            tag_mapping = self.config_manager.get_tag_mapping(server_id, data_point.tag_name)
            if not tag_mapping:
                logger.warning(f"No mapping found for {data_point.tag_name}")
                return

            # Apply scaling
            if tag_mapping.scale_factor != 1.0 or tag_mapping.offset != 0.0:
                data_point.value = (data_point.value * tag_mapping.scale_factor) + tag_mapping.offset

            # Create Sparkplug metric
            metric = {
                'name': tag_mapping.sparkplug_metric_name,
                'value': data_point.value,
                'timestamp': int(data_point.timestamp.timestamp() * 1000),
                'quality': data_point.quality,
                'properties': {
                    'unit': tag_mapping.unit,
                    'opcua_node': data_point.tag_name,
                    'server_id': server_id
                }
            }

            # Publish via Sparkplug
            await self.sparkplug_client.publish_device_data(
                device_id=tag_mapping.machine_id or 'default',
                metrics=[metric]
            )

            # Process for OEE if mapped
            if tag_mapping.oee_metric_type:
                await self.data_processor.process_oee_metric(
                    machine_id=tag_mapping.machine_id,
                    metric_type=tag_mapping.oee_metric_type,
                    value=data_point.value,
                    timestamp=data_point.timestamp
                )

            # Update database
            await self.update_node_mapping(
                server_id,
                data_point.tag_name,
                data_point.value,
                data_point.timestamp,
                data_point.quality
            )

        except Exception as e:
            logger.error(f"Error handling OPC-UA data: {e}")

    async def update_server_status(self, server_id: str, status: str, error: str = None):
        """Update server status in database"""
        try:
            server = await OPCUAServerConnection.objects.aget(server_id=server_id)
            server.status = status
            if status == 'CONNECTED':
                server.last_connection = django_timezone.now()
            elif status in ['DISCONNECTED', 'ERROR']:
                server.last_disconnection = django_timezone.now()
            if error:
                server.last_error = error
            await server.asave()
        except Exception as e:
            logger.error(f"Error updating server status: {e}")

    async def update_node_mapping(self, server_id: str, node_id: str,
                                  value: Any, timestamp: datetime, quality: int):
        """Update node mapping with latest value"""
        try:
            mapping = await OPCUANodeMapping.objects.select_for_update().aget(
                server__server_id=server_id,
                opcua_node_id=node_id
            )
            mapping.last_value = str(value)
            mapping.last_timestamp = timestamp
            mapping.last_quality = quality
            await mapping.asave()
        except Exception as e:
            logger.debug(f"Error updating node mapping: {e}")

    async def stop(self):
        """Stop the bridge"""
        self.running = False
        logger.info("Stopping OPC-UA to Sparkplug B bridge")

        # Disconnect OPC-UA clients
        for server_id, client in self.opcua_clients.items():
            try:
                await client.disconnect()
                await self.update_server_status(server_id, 'DISCONNECTED')
            except Exception as e:
                logger.error(f"Error disconnecting {server_id}: {e}")

        # Disconnect MQTT
        await self.sparkplug_client.disconnect()

        # Cancel tasks
        for task in self.tasks:
            task.cancel()

    async def run_forever(self):
        """Run the bridge until stopped"""
        await self.start()

        while self.running:
            await asyncio.sleep(1)

            # Check client health
            for server_id, client in list(self.opcua_clients.items()):
                if client.status.value == 'ERROR':
                    logger.warning(f"Client {server_id} in error state, will reconnect")


class Command(BaseCommand):
    help = 'Run OPC-UA agent for data collection and Sparkplug B publishing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--config-file',
            type=str,
            help='Path to configuration file (YAML or JSON)'
        )
        parser.add_argument(
            '--log-level',
            type=str,
            default='INFO',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            help='Logging level'
        )
        parser.add_argument(
            '--metrics-port',
            type=int,
            default=8003,
            help='Prometheus metrics port'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually connecting to servers'
        )
        parser.add_argument(
            '--discover',
            action='store_true',
            help='Run discovery mode to browse available OPC-UA nodes'
        )
        parser.add_argument(
            '--server-id',
            type=str,
            help='Specific server ID to connect to'
        )
        parser.add_argument(
            '--mqtt-host',
            type=str,
            help='MQTT broker hostname'
        )
        parser.add_argument(
            '--mqtt-port',
            type=int,
            default=1883,
            help='MQTT broker port'
        )
        parser.add_argument(
            '--group-id',
            type=str,
            default='OEE_System',
            help='Sparkplug group ID'
        )
        parser.add_argument(
            '--node-id',
            type=str,
            default='OPCUA_Bridge',
            help='Sparkplug node ID'
        )

    def handle(self, *args, **options):
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, options['log_level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Start Prometheus metrics server
        if not options['dry_run']:
            start_http_server(options['metrics_port'])
            self.stdout.write(f"Prometheus metrics available at http://localhost:{options['metrics_port']}/metrics")

        # Run async main
        try:
            asyncio.run(self.async_main(options))
        except KeyboardInterrupt:
            self.stdout.write("\nShutdown requested...")
        except Exception as e:
            raise CommandError(f"Fatal error: {e}")

    async def async_main(self, options):
        """Async main function"""
        # Load configuration
        config_manager = OPCUAConfigManager()

        if options['config_file']:
            if not config_manager.load_config(options['config_file']):
                raise CommandError(f"Failed to load config from {options['config_file']}")
        else:
            # Load from database
            await self.load_config_from_db(config_manager)

        # Filter by server_id if specified
        if options['server_id']:
            servers = {options['server_id']: config_manager.servers.get(options['server_id'])}
            if not servers[options['server_id']]:
                raise CommandError(f"Server {options['server_id']} not found")
            config_manager.servers = servers

        # Discovery mode
        if options['discover']:
            await self.run_discovery(config_manager)
            return

        # Dry run mode
        if options['dry_run']:
            self.stdout.write("DRY RUN MODE - Configuration loaded:")
            for server_id, server in config_manager.servers.items():
                self.stdout.write(f"\nServer: {server_id}")
                self.stdout.write(f"  Endpoint: {server.endpoint_url}")
                self.stdout.write(f"  Tags: {len(server.tags)}")
            return

        # Initialize components
        sparkplug_config = SparkplugConfig(
            broker_host=options.get('mqtt_host') or getattr(settings, 'MQTT_BROKER_HOST', 'localhost'),
            broker_port=options.get('mqtt_port') or 1883,
            group_id=options['group_id'],
            node_id=options['node_id'],
            username=getattr(settings, 'MQTT_USERNAME', None),
            password=getattr(settings, 'MQTT_PASSWORD', None),
            use_tls=getattr(settings, 'MQTT_USE_TLS', False)
        )

        sparkplug_client = SparkplugMQTTClient(sparkplug_config)
        data_processor = DataProcessor()

        # Create bridge
        bridge = OPCUAToSparkplugBridge(
            config_manager,
            sparkplug_client,
            data_processor
        )

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown(bridge))
            )

        # Run bridge
        self.stdout.write("Starting OPC-UA to Sparkplug B bridge...")
        await bridge.run_forever()

    async def load_config_from_db(self, config_manager: OPCUAConfigManager):
        """Load configuration from database"""
        servers = OPCUAServerConnection.objects.filter(enabled=True).prefetch_related('opcuanodemapping_set')

        async for server in servers:
            # Convert to config format
            server_config = {
                'id': server.server_id,
                'name': server.name,
                'endpoint_url': server.endpoint_url,
                'enabled': server.enabled,
                'security_mode': server.security_mode,
                'security_policy': server.security_policy,
                'auth_mode': server.auth_mode,
                'username': server.username,
                'password': server.password,
                'client_cert_path': server.client_cert_path,
                'client_key_path': server.client_key_path,
                'server_cert_path': server.server_cert_path,
                'session_timeout_ms': server.session_timeout_ms,
                'keep_alive_interval_ms': server.keep_alive_interval_ms,
                'reconnect_interval_s': server.reconnect_interval_s,
                'max_reconnect_attempts': server.max_reconnect_attempts,
                'publishing_interval_ms': server.publishing_interval_ms,
                'max_notifications_per_publish': server.max_notifications_per_publish,
                'max_concurrent_reads': server.max_concurrent_reads,
                'batch_read_size': server.batch_read_size,
                'tags': []
            }

            # Add tags
            async for mapping in server.opcuanodemapping_set.filter(enabled=True):
                tag_config = {
                    'opcua_node_id': mapping.opcua_node_id,
                    'sparkplug_metric_name': mapping.sparkplug_metric_name,
                    'display_name': mapping.display_name,
                    'data_type': mapping.data_type,
                    'scale_factor': mapping.scale_factor,
                    'offset': mapping.offset,
                    'unit': mapping.unit,
                    'sampling_interval_ms': mapping.sampling_interval_ms,
                    'deadband_type': mapping.deadband_type,
                    'deadband_value': mapping.deadband_value,
                    'oee_metric_type': mapping.oee_metric_type,
                    'machine_id': mapping.machine_id,
                    'line_id': mapping.line_id
                }
                server_config['tags'].append(tag_config)

            # Add to config manager
            config_manager.servers[server.server_id] = server_config

        self.stdout.write(f"Loaded {len(config_manager.servers)} servers from database")

    async def run_discovery(self, config_manager: OPCUAConfigManager):
        """Run OPC-UA discovery mode"""
        self.stdout.write("Running OPC-UA discovery mode...")

        for server_id, server_config in config_manager.servers.items():
            self.stdout.write(f"\nDiscovering nodes on {server_id}...")

            try:
                # Create client
                opcua_config = OPCUAConfig(
                    host=server_config.endpoint_url.split('//')[1].split(':')[0],
                    port=int(server_config.endpoint_url.split(':')[-1].split('/')[0]),
                    endpoint_url=server_config.endpoint_url,
                    security_mode=server_config.security_mode,
                    auth_mode=server_config.auth_mode,
                    username=server_config.username,
                    password=server_config.password
                )

                client = OPCUAClient(opcua_config)

                # Connect
                if await client.connect():
                    # Get server info
                    info = await client.get_server_info()
                    self.stdout.write(f"Server info: {json.dumps(info, indent=2)}")

                    # Browse nodes
                    nodes = await client.browse_nodes(max_depth=5)
                    self.stdout.write(f"Found {len(nodes)} nodes:")

                    for node in nodes[:50]:  # Limit output
                        self.stdout.write(f"  {node['node_id']}: {node['browse_name']} ({node['node_class']})")
                        if 'value' in node:
                            self.stdout.write(f"    Value: {node['value']}")

                    # Disconnect
                    await client.disconnect()
                else:
                    self.stdout.write(f"Failed to connect to {server_id}")

            except Exception as e:
                self.stdout.write(f"Error discovering {server_id}: {e}")

    async def shutdown(self, bridge):
        """Shutdown handler"""
        logger.info("Shutdown signal received")
        await bridge.stop()
        sys.exit(0)