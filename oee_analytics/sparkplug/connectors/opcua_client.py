"""
OPC-UA Client Connector
Production-ready implementation with subscription management and monitored items
Supports certificate-based authentication and automatic reconnection
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, Callable, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import ssl
from pathlib import Path

from asyncua import Client, ua, Node
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.ua.uaerrors import UaError, BadConnectionClosed, BadTimeout
from asyncua.common.subscription import Subscription, DataChangeNotif

from prometheus_client import Counter, Histogram, Gauge

from .base import (
    BasePLCConnector, PLCConnectionConfig, PLCTagDefinition,
    PLCDataPoint, PLCStatus, PLCConnectionError, PLCDataError
)

# Prometheus metrics
OPCUA_CONNECTIONS = Gauge('opcua_connections_active', 'Active OPC-UA connections', ['server'])
OPCUA_SUBSCRIPTIONS = Gauge('opcua_subscriptions_active', 'Active OPC-UA subscriptions', ['server'])
OPCUA_MONITORED_ITEMS = Gauge('opcua_monitored_items_total', 'Total monitored items', ['server'])
OPCUA_DATA_CHANGES = Counter('opcua_data_changes_total', 'Total data change notifications', ['server', 'node'])
OPCUA_QUALITY_ERRORS = Counter('opcua_quality_errors_total', 'Quality errors received', ['server', 'quality'])
OPCUA_RECONNECTS = Counter('opcua_reconnects_total', 'OPC-UA reconnection attempts', ['server'])
OPCUA_READ_TIME = Histogram('opcua_read_duration_seconds', 'Time to read OPC-UA values')


class OPCUASecurityMode(Enum):
    """OPC-UA security modes"""
    NONE = "None"
    SIGN = "Sign"
    SIGN_AND_ENCRYPT = "SignAndEncrypt"


class OPCUAAuthMode(Enum):
    """OPC-UA authentication modes"""
    ANONYMOUS = "Anonymous"
    USERNAME_PASSWORD = "UsernamePassword"
    CERTIFICATE = "Certificate"


@dataclass
class OPCUAConfig(PLCConnectionConfig):
    """Extended configuration for OPC-UA connections"""
    # Server settings (required fields must come before optional ones)
    endpoint_url: str = "opc.tcp://localhost:4840"
    namespace_idx: int = 2

    # Security settings
    security_mode: OPCUASecurityMode = OPCUASecurityMode.SIGN_AND_ENCRYPT
    security_policy: str = "Basic256Sha256"
    auth_mode: OPCUAAuthMode = OPCUAAuthMode.CERTIFICATE

    # Certificate paths (for certificate auth)
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    server_cert_path: Optional[str] = None

    # Username/password (for username auth)
    username: Optional[str] = None
    password: Optional[str] = None

    # Connection settings
    session_timeout: int = 30000  # ms
    secure_channel_timeout: int = 60000  # ms
    keep_alive_interval: int = 10000  # ms
    reconnect_interval: int = 5  # seconds
    max_reconnect_attempts: int = -1  # infinite

    # Subscription settings
    publishing_interval: int = 250  # ms
    max_notifications_per_publish: int = 1000
    priority: int = 0

    # Monitored item defaults
    default_sampling_interval: int = 250  # ms
    default_queue_size: int = 10
    default_discard_oldest: bool = True
    default_deadband_type: int = 1  # 0=None, 1=Absolute, 2=Percent
    default_deadband_value: float = 0.0

    # Browse settings
    max_browse_nodes: int = 1000
    browse_timeout: int = 30000  # ms

    # Performance
    max_concurrent_reads: int = 100
    batch_read_size: int = 50
    read_timeout: int = 10000  # ms


@dataclass
class MonitoredItemConfig:
    """Configuration for a monitored item"""
    node_id: str
    display_name: str
    sampling_interval: int = 250
    queue_size: int = 10
    discard_oldest: bool = True
    deadband_type: int = 1
    deadband_value: float = 0.0
    data_change_filter: Optional[ua.DataChangeFilter] = None
    callback: Optional[Callable] = None


class OPCUASubscriptionHandler:
    """Handler for OPC-UA subscription data changes"""

    def __init__(self, client: 'OPCUAClient'):
        self.client = client
        self.logger = logging.getLogger(__name__)

    def datachange_notification(self, node: Node, val, data: DataChangeNotif):
        """Handle data change notifications"""
        try:
            node_id = node.nodeid.to_string()

            # Update metrics
            OPCUA_DATA_CHANGES.labels(
                server=self.client.config.endpoint_url,
                node=node_id
            ).inc()

            # Check quality
            if data.monitored_item.Value.StatusCode:
                status_code = data.monitored_item.Value.StatusCode.value
                if status_code != 0:  # Not Good
                    quality = self._get_quality_string(status_code)
                    OPCUA_QUALITY_ERRORS.labels(
                        server=self.client.config.endpoint_url,
                        quality=quality
                    ).inc()
                    self.logger.warning(f"Bad quality for {node_id}: {quality}")

            # Create data point
            data_point = PLCDataPoint(
                tag_name=node_id,
                value=val,
                timestamp=data.monitored_item.Value.SourceTimestamp or datetime.now(timezone.utc),
                quality=self._map_quality(data.monitored_item.Value.StatusCode),
                metadata={
                    'server_timestamp': data.monitored_item.Value.ServerTimestamp,
                    'source_timestamp': data.monitored_item.Value.SourceTimestamp,
                    'status_code': data.monitored_item.Value.StatusCode.value if data.monitored_item.Value.StatusCode else 0
                }
            )

            # Process through client callback
            if self.client.data_callback:
                asyncio.create_task(self.client.data_callback(data_point))

        except Exception as e:
            self.logger.error(f"Error processing data change: {e}")

    def event_notification(self, event):
        """Handle event notifications"""
        self.logger.debug(f"Event notification: {event}")

    def status_change_notification(self, status):
        """Handle status change notifications"""
        self.logger.info(f"Subscription status change: {status}")

    def _get_quality_string(self, status_code: int) -> str:
        """Map OPC-UA status code to quality string"""
        if status_code & 0x40000000:
            return "Uncertain"
        elif status_code & 0x80000000:
            return "Bad"
        return "Good"

    def _map_quality(self, status_code) -> int:
        """Map OPC-UA status to quality score (0-100)"""
        if not status_code:
            return 100

        code = status_code.value if hasattr(status_code, 'value') else status_code

        if code == 0:
            return 100  # Good
        elif code & 0x40000000:
            return 50   # Uncertain
        else:
            return 0    # Bad


class OPCUAClient(BasePLCConnector):
    """
    OPC-UA Client Connector with subscription support
    Implements monitored items, deadband, and quality tracking
    """

    def __init__(self, config: OPCUAConfig):
        super().__init__(config)
        self.config: OPCUAConfig = config
        self.client: Optional[Client] = None
        self.subscription: Optional[Subscription] = None
        self.monitored_items: Dict[str, Any] = {}
        self.handler = OPCUASubscriptionHandler(self)
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0
        self.data_callback: Optional[Callable] = None

    async def connect(self) -> bool:
        """Establish OPC-UA connection with security"""
        try:
            self.logger.info(f"Connecting to OPC-UA server: {self.config.endpoint_url}")

            # Create client
            self.client = Client(url=self.config.endpoint_url)

            # Configure security
            await self._configure_security()

            # Configure session
            self.client.session_timeout = self.config.session_timeout
            self.client.secure_channel_timeout = self.config.secure_channel_timeout

            # Connect
            await self.client.connect()

            # Update metrics
            OPCUA_CONNECTIONS.labels(server=self.config.endpoint_url).set(1)

            # Create subscription
            await self._create_subscription()

            self.status = PLCStatus.CONNECTED
            self.logger.info(f"Connected to OPC-UA server: {self.config.endpoint_url}")

            # Start keep-alive
            asyncio.create_task(self._keep_alive())

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to OPC-UA server: {e}")
            self.status = PLCStatus.ERROR
            self.last_error = str(e)
            OPCUA_CONNECTIONS.labels(server=self.config.endpoint_url).set(0)

            # Start reconnection task
            if not self._reconnect_task:
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())

            return False

    async def _configure_security(self):
        """Configure OPC-UA security settings"""
        if self.config.security_mode == OPCUASecurityMode.NONE:
            return

        # Set security policy
        if self.config.security_mode in [OPCUASecurityMode.SIGN, OPCUASecurityMode.SIGN_AND_ENCRYPT]:
            if self.config.security_policy == "Basic256Sha256":
                await self.client.set_security(
                    SecurityPolicyBasic256Sha256,
                    self.config.client_cert_path,
                    self.config.client_key_path,
                    self.config.server_cert_path,
                    ua.MessageSecurityMode.SignAndEncrypt if self.config.security_mode == OPCUASecurityMode.SIGN_AND_ENCRYPT else ua.MessageSecurityMode.Sign
                )

        # Set authentication
        if self.config.auth_mode == OPCUAAuthMode.USERNAME_PASSWORD:
            self.client.set_user(self.config.username)
            self.client.set_password(self.config.password)

    async def _create_subscription(self):
        """Create OPC-UA subscription"""
        if not self.client:
            return

        try:
            params = ua.CreateSubscriptionParameters()
            params.RequestedPublishingInterval = self.config.publishing_interval
            params.RequestedMaxKeepAliveCount = 10
            params.RequestedLifetimeCount = 3000
            params.MaxNotificationsPerPublish = self.config.max_notifications_per_publish
            params.PublishingEnabled = True
            params.Priority = self.config.priority

            self.subscription = await self.client.create_subscription(
                params,
                self.handler
            )

            OPCUA_SUBSCRIPTIONS.labels(server=self.config.endpoint_url).set(1)
            self.logger.info(f"Created subscription with ID: {self.subscription.subscription_id}")

        except Exception as e:
            self.logger.error(f"Failed to create subscription: {e}")
            raise

    async def add_monitored_item(self, config: MonitoredItemConfig) -> bool:
        """Add a monitored item to the subscription"""
        if not self.subscription:
            self.logger.error("No active subscription")
            return False

        try:
            # Get node
            node = self.client.get_node(config.node_id)

            # Create monitoring parameters
            params = ua.MonitoredItemCreateRequest()
            params.ItemToMonitor.NodeId = node.nodeid
            params.ItemToMonitor.AttributeId = ua.AttributeIds.Value
            params.MonitoringMode = ua.MonitoringMode.Reporting

            # Configure sampling
            params.RequestedParameters.ClientHandle = len(self.monitored_items)
            params.RequestedParameters.SamplingInterval = config.sampling_interval
            params.RequestedParameters.QueueSize = config.queue_size
            params.RequestedParameters.DiscardOldest = config.discard_oldest

            # Configure deadband filter
            if config.deadband_value > 0:
                data_filter = ua.DataChangeFilter()
                data_filter.Trigger = ua.DataChangeTrigger.StatusValue
                data_filter.DeadbandType = config.deadband_type
                data_filter.DeadbandValue = config.deadband_value
                params.RequestedParameters.Filter = data_filter

            # Create monitored item
            items = await self.subscription.create_monitored_items([params])

            if items and items[0].StatusCode.is_good():
                self.monitored_items[config.node_id] = {
                    'handle': items[0].MonitoredItemId,
                    'node': node,
                    'config': config
                }

                OPCUA_MONITORED_ITEMS.labels(server=self.config.endpoint_url).set(
                    len(self.monitored_items)
                )

                self.logger.info(f"Added monitored item: {config.node_id}")
                return True
            else:
                self.logger.error(f"Failed to add monitored item {config.node_id}: {items[0].StatusCode}")
                return False

        except Exception as e:
            self.logger.error(f"Error adding monitored item {config.node_id}: {e}")
            return False

    async def remove_monitored_item(self, node_id: str) -> bool:
        """Remove a monitored item from the subscription"""
        if node_id not in self.monitored_items:
            return False

        try:
            handle = self.monitored_items[node_id]['handle']
            await self.subscription.delete_monitored_items([handle])
            del self.monitored_items[node_id]

            OPCUA_MONITORED_ITEMS.labels(server=self.config.endpoint_url).set(
                len(self.monitored_items)
            )

            self.logger.info(f"Removed monitored item: {node_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error removing monitored item {node_id}: {e}")
            return False

    async def read_tag(self, tag: PLCTagDefinition) -> PLCDataPoint:
        """Read a single tag value"""
        if not self.client:
            raise PLCConnectionError("Not connected to OPC-UA server")

        try:
            with OPCUA_READ_TIME.time():
                node = self.client.get_node(tag.address)
                value = await node.read_value()

                # Get additional attributes
                data_value = await node.read_data_value()

                return PLCDataPoint(
                    tag_name=tag.name,
                    value=value,
                    timestamp=data_value.SourceTimestamp or datetime.now(timezone.utc),
                    quality=self._map_quality(data_value.StatusCode),
                    metadata={
                        'server_timestamp': data_value.ServerTimestamp,
                        'status_code': data_value.StatusCode.value if data_value.StatusCode else 0
                    }
                )

        except Exception as e:
            self.logger.error(f"Error reading tag {tag.name}: {e}")
            raise PLCDataError(f"Failed to read tag {tag.name}: {e}")

    async def read_tags_batch(self, tags: List[PLCTagDefinition]) -> List[PLCDataPoint]:
        """Read multiple tags in batch"""
        if not self.client:
            raise PLCConnectionError("Not connected to OPC-UA server")

        results = []

        # Process in batches
        for i in range(0, len(tags), self.config.batch_read_size):
            batch = tags[i:i + self.config.batch_read_size]

            try:
                nodes = [self.client.get_node(tag.address) for tag in batch]
                values = await asyncio.gather(
                    *[node.read_data_value() for node in nodes],
                    return_exceptions=True
                )

                for tag, value in zip(batch, values):
                    if isinstance(value, Exception):
                        self.logger.error(f"Error reading {tag.name}: {value}")
                        results.append(PLCDataPoint(
                            tag_name=tag.name,
                            value=None,
                            timestamp=datetime.now(timezone.utc),
                            quality=0,
                            metadata={'error': str(value)}
                        ))
                    else:
                        results.append(PLCDataPoint(
                            tag_name=tag.name,
                            value=value.Value.Value,
                            timestamp=value.SourceTimestamp or datetime.now(timezone.utc),
                            quality=self._map_quality(value.StatusCode),
                            metadata={
                                'server_timestamp': value.ServerTimestamp,
                                'status_code': value.StatusCode.value if value.StatusCode else 0
                            }
                        ))

            except Exception as e:
                self.logger.error(f"Error in batch read: {e}")

        return results

    async def write_tag(self, tag: PLCTagDefinition, value: Any) -> bool:
        """Write a value to a tag (if supported)"""
        if not self.client:
            raise PLCConnectionError("Not connected to OPC-UA server")

        try:
            node = self.client.get_node(tag.address)
            await node.write_value(value)
            return True
        except Exception as e:
            self.logger.error(f"Error writing tag {tag.name}: {e}")
            return False

    async def browse_nodes(self, start_node: Optional[str] = None, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Browse OPC-UA address space for available nodes"""
        if not self.client:
            raise PLCConnectionError("Not connected to OPC-UA server")

        nodes = []

        try:
            if start_node:
                root = self.client.get_node(start_node)
            else:
                root = self.client.nodes.objects

            await self._browse_recursive(root, nodes, 0, max_depth)

        except Exception as e:
            self.logger.error(f"Error browsing nodes: {e}")

        return nodes

    async def _browse_recursive(self, node: Node, nodes: List, depth: int, max_depth: int):
        """Recursively browse nodes"""
        if depth >= max_depth or len(nodes) >= self.config.max_browse_nodes:
            return

        try:
            # Get node info
            browse_name = await node.read_browse_name()
            node_class = await node.read_node_class()

            node_info = {
                'node_id': node.nodeid.to_string(),
                'browse_name': browse_name.to_string(),
                'node_class': node_class.name,
                'depth': depth
            }

            # If it's a variable, get additional info
            if node_class == ua.NodeClass.Variable:
                try:
                    value = await node.read_value()
                    data_type = await node.read_data_type()
                    node_info['value'] = str(value)
                    node_info['data_type'] = str(data_type)
                except:
                    pass

            nodes.append(node_info)

            # Browse children
            children = await node.get_children()
            for child in children[:10]:  # Limit children per node
                await self._browse_recursive(child, nodes, depth + 1, max_depth)

        except Exception as e:
            self.logger.debug(f"Error browsing node: {e}")

    async def disconnect(self):
        """Disconnect from OPC-UA server"""
        try:
            # Cancel reconnect task
            if self._reconnect_task:
                self._reconnect_task.cancel()
                self._reconnect_task = None

            # Delete subscription
            if self.subscription:
                await self.subscription.delete()
                self.subscription = None
                OPCUA_SUBSCRIPTIONS.labels(server=self.config.endpoint_url).set(0)

            # Disconnect client
            if self.client:
                await self.client.disconnect()
                self.client = None
                OPCUA_CONNECTIONS.labels(server=self.config.endpoint_url).set(0)

            self.status = PLCStatus.DISCONNECTED
            self.monitored_items.clear()
            OPCUA_MONITORED_ITEMS.labels(server=self.config.endpoint_url).set(0)

            self.logger.info(f"Disconnected from OPC-UA server: {self.config.endpoint_url}")

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")

    async def _keep_alive(self):
        """Keep connection alive with periodic reads"""
        while self.status == PLCStatus.CONNECTED:
            try:
                if self.client:
                    # Read server status
                    server_node = self.client.nodes.server
                    status = await server_node.read_value()

                await asyncio.sleep(self.config.keep_alive_interval / 1000)

            except Exception as e:
                self.logger.warning(f"Keep-alive failed: {e}")
                self.status = PLCStatus.ERROR

                # Trigger reconnection
                if not self._reconnect_task:
                    self._reconnect_task = asyncio.create_task(self._reconnect_loop())
                break

    async def _reconnect_loop(self):
        """Automatic reconnection with exponential backoff"""
        while (self.config.max_reconnect_attempts < 0 or
               self._reconnect_attempts < self.config.max_reconnect_attempts):

            self._reconnect_attempts += 1
            wait_time = min(60, self.config.reconnect_interval * (2 ** min(self._reconnect_attempts - 1, 5)))

            self.logger.info(f"Reconnection attempt {self._reconnect_attempts} in {wait_time} seconds...")
            await asyncio.sleep(wait_time)

            try:
                # Disconnect if still connected
                if self.client:
                    try:
                        await self.client.disconnect()
                    except:
                        pass

                # Reconnect
                if await self.connect():
                    self.logger.info("Reconnection successful")
                    self._reconnect_attempts = 0
                    OPCUA_RECONNECTS.labels(server=self.config.endpoint_url).inc()

                    # Restore monitored items
                    for node_id, item_info in list(self.monitored_items.items()):
                        await self.add_monitored_item(item_info['config'])

                    break

            except Exception as e:
                self.logger.error(f"Reconnection failed: {e}")

        self._reconnect_task = None

    def _map_quality(self, status_code) -> int:
        """Map OPC-UA status to quality score (0-100)"""
        if not status_code:
            return 100

        code = status_code.value if hasattr(status_code, 'value') else status_code

        if code == 0:
            return 100  # Good
        elif code & 0x40000000:
            return 50   # Uncertain
        else:
            return 0    # Bad

    async def get_server_info(self) -> Dict[str, Any]:
        """Get OPC-UA server information"""
        if not self.client:
            return {}

        try:
            server = self.client.nodes.server

            info = {
                'product_name': await server.get_child(["0:ServerStatus", "0:BuildInfo", "0:ProductName"]).read_value(),
                'manufacturer': await server.get_child(["0:ServerStatus", "0:BuildInfo", "0:ManufacturerName"]).read_value(),
                'software_version': await server.get_child(["0:ServerStatus", "0:BuildInfo", "0:SoftwareVersion"]).read_value(),
                'current_time': await server.get_child(["0:ServerStatus", "0:CurrentTime"]).read_value(),
                'start_time': await server.get_child(["0:ServerStatus", "0:StartTime"]).read_value(),
                'state': await server.get_child(["0:ServerStatus", "0:State"]).read_value(),
            }

            return info

        except Exception as e:
            self.logger.error(f"Error getting server info: {e}")
            return {}