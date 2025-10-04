"""
PLC Configuration API Views
Provides endpoints for machine/PLC configuration management
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from oee_analytics.models.asset_hierarchy import Machine
from .serializers_plc import (
    PLCConnectionSerializer,
    PLCConnectionTestSerializer,
    PLCTagDefinitionSerializer,
    PLCTagDiscoverySerializer
)
from oee_analytics.sparkplug.connectors.base import (
    PLCConnectorFactory,
    PLCConnectionConfig,
    PLCConnectionError
)

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class MachineConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for machine/PLC configuration management
    Provides CRUD operations with protocol-specific validation
    """
    queryset = Machine.objects.all()
    serializer_class = PLCConnectionSerializer
    permission_classes = [AllowAny]  # Change to IsAuthenticated in production

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()

        # Filter by protocol
        protocol = self.request.query_params.get('protocol')
        if protocol:
            queryset = queryset.filter(protocol=protocol)

        # Filter by status
        machine_status = self.request.query_params.get('status')
        if machine_status:
            queryset = queryset.filter(status=machine_status)

        # Filter by active status
        active = self.request.query_params.get('active')
        if active is not None:
            queryset = queryset.filter(active=active.lower() in ['true', '1', 'yes'])

        # Filter by line
        line_id = self.request.query_params.get('line_id')
        if line_id:
            queryset = queryset.filter(cell__line__line_id=line_id)

        return queryset.select_related('cell__line__area__site')

    def create(self, request, *args, **kwargs):
        """Create with detailed error logging"""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.error(f"Machine creation failed: {str(e)}")
            logger.error(f"Validation errors: {serializer.errors if hasattr(serializer, 'errors') else 'N/A'}")
            logger.error(f"Request data: {request.data}")
            raise

    def perform_create(self, serializer):
        """Create machine and notify via WebSocket"""
        machine = serializer.save()

        # Notify configuration update via WebSocket
        self._notify_config_update({
            'action': 'created',
            'machine_id': machine.machine_id,
            'machine_name': machine.name,
            'protocol': machine.protocol
        })

        logger.info(f"Machine created: {machine.name} ({machine.protocol})")

    def perform_update(self, serializer):
        """Update machine and notify via WebSocket"""
        machine = serializer.save()

        # Notify configuration update via WebSocket
        self._notify_config_update({
            'action': 'updated',
            'machine_id': machine.machine_id,
            'machine_name': machine.name,
            'protocol': machine.protocol
        })

        logger.info(f"Machine updated: {machine.name} ({machine.protocol})")

    def perform_destroy(self, instance):
        """Delete machine and notify via WebSocket"""
        machine_id = instance.machine_id
        machine_name = instance.name

        instance.delete()

        # Notify configuration update via WebSocket
        self._notify_config_update({
            'action': 'deleted',
            'machine_id': machine_id,
            'machine_name': machine_name
        })

        logger.info(f"Machine deleted: {machine_name}")

    def _notify_config_update(self, data: Dict[str, Any]):
        """Send configuration update notification via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "machine_config",
                {
                    "type": "config_update",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": data
                }
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """
        Test PLC connection without saving configuration
        POST /api/machines/{id}/test_connection/
        """
        machine = self.get_object()

        try:
            # Create temporary connector config
            config = self._create_connector_config(machine)

            # Get connector factory
            connector = PLCConnectorFactory.create_connector(
                plc_type=machine.protocol,
                config=config,
                logger=logger
            )

            # Test connection asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            success = loop.run_until_complete(connector.connect())

            if success:
                # Get device info
                health_info = loop.run_until_complete(connector.health_check())

                # Disconnect
                loop.run_until_complete(connector.disconnect())
                loop.close()

                # Notify via WebSocket
                self._notify_test_result({
                    'machine_id': machine.machine_id,
                    'success': True,
                    'health_info': health_info
                })

                return Response({
                    'success': True,
                    'message': 'Connection successful',
                    'device_info': health_info
                })
            else:
                loop.close()
                return Response({
                    'success': False,
                    'message': 'Connection failed',
                    'error': connector.last_error
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return Response({
                'success': False,
                'message': 'Connection test failed',
                'error': str(e),
                'diagnostics': self._get_error_diagnostics(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def discover_tags(self, request, pk=None):
        """
        Auto-discover tags/variables from PLC
        POST /api/machines/{id}/discover_tags/
        """
        machine = self.get_object()

        try:
            # Create connector config
            config = self._create_connector_config(machine)

            # Get connector
            connector = PLCConnectorFactory.create_connector(
                plc_type=machine.protocol,
                config=config,
                logger=logger
            )

            # Run discovery
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Connect
            connected = loop.run_until_complete(connector.connect())
            if not connected:
                loop.close()
                return Response({
                    'success': False,
                    'message': 'Failed to connect to PLC'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Discover tags
            discovered_tags = loop.run_until_complete(connector.discover_tags())

            # Disconnect
            loop.run_until_complete(connector.disconnect())
            loop.close()

            # Serialize tags
            tag_serializer = PLCTagDefinitionSerializer(discovered_tags, many=True)

            # Notify via WebSocket
            self._notify_discovery_progress({
                'machine_id': machine.machine_id,
                'tags_found': len(discovered_tags),
                'completed': True
            })

            return Response({
                'success': True,
                'machine_id': machine.machine_id,
                'machine_name': machine.name,
                'tags_found': len(discovered_tags),
                'tags': tag_serializer.data
            })

        except Exception as e:
            logger.error(f"Tag discovery failed: {e}")
            return Response({
                'success': False,
                'message': 'Tag discovery failed',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def reload_connection(self, request, pk=None):
        """
        Hot-reload PLC connection after configuration changes
        POST /api/machines/{id}/reload_connection/
        """
        machine = self.get_object()

        try:
            # Reload connector from factory cache
            PLCConnectorFactory.reload_connector(machine.machine_id)

            return Response({
                'success': True,
                'message': f'Connection reloaded for {machine.name}',
                'machine_id': machine.machine_id
            })

        except Exception as e:
            logger.error(f"Failed to reload connection: {e}")
            return Response({
                'success': False,
                'message': 'Failed to reload connection',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _create_connector_config(self, machine: Machine) -> PLCConnectionConfig:
        """Create connector configuration from machine model"""
        protocol_config = machine.metadata or {}

        return PLCConnectionConfig(
            host=machine.ip_address,
            port=machine.port or self._get_default_port(machine.protocol),
            timeout=protocol_config.get('timeout', 5.0),
            rack=protocol_config.get('rack', 0),
            slot=protocol_config.get('slot', 0 if machine.protocol == 'ETHERNET_IP' else 1),
            username=protocol_config.get('username'),
            password=protocol_config.get('password'),
            use_tls=protocol_config.get('use_tls', False),
            ca_cert_path=protocol_config.get('ca_cert_path'),
            client_cert_path=protocol_config.get('client_cert_path'),
            client_key_path=protocol_config.get('client_key_path')
        )

    def _get_default_port(self, protocol: str) -> int:
        """Get default port for protocol"""
        defaults = {
            'ETHERNET_IP': 44818,
            'S7': 102,
            'OPCUA': 4840,
            'MODBUS': 502,
            'HTTP': 80,
            'MQTT': 1883
        }
        return defaults.get(protocol, 502)

    def _notify_test_result(self, data: Dict[str, Any]):
        """Send test result notification via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "machine_config",
                {
                    "type": "connection_test_result",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": data
                }
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")

    def _notify_discovery_progress(self, data: Dict[str, Any]):
        """Send discovery progress notification via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "machine_config",
                {
                    "type": "tag_discovery_progress",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": data
                }
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")

    def _get_error_diagnostics(self, error: Exception) -> Dict[str, Any]:
        """Get diagnostic information for connection errors"""
        diagnostics = {
            'error_type': type(error).__name__,
            'suggestions': []
        }

        error_str = str(error).lower()

        # Common connection errors and suggestions
        if 'timeout' in error_str or 'timed out' in error_str:
            diagnostics['suggestions'].extend([
                'Check if PLC is powered on and connected to network',
                'Verify IP address is correct',
                'Check firewall settings',
                'Increase timeout value in configuration'
            ])
        elif 'connection refused' in error_str:
            diagnostics['suggestions'].extend([
                'Verify port number is correct',
                'Check if PLC service is running',
                'Ensure PLC allows remote connections'
            ])
        elif 'host not found' in error_str or 'name resolution' in error_str:
            diagnostics['suggestions'].extend([
                'Check IP address format',
                'Verify network connectivity',
                'Try using IP address instead of hostname'
            ])
        elif 'authentication' in error_str or 'unauthorized' in error_str:
            diagnostics['suggestions'].extend([
                'Verify username and password',
                'Check authentication mode configuration',
                'Ensure PLC user has necessary permissions'
            ])

        return diagnostics


@api_view(['POST'])
@permission_classes([AllowAny])
def test_plc_connection_standalone(request):
    """
    Test PLC connection without requiring existing machine record
    POST /api/plc/test-connection/
    Body: {ip_address, port, protocol, protocol_config, timeout}
    """
    serializer = PLCConnectionTestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        # Extract protocol-specific configuration
        protocol_config = data.get('protocol_config', {})
        protocol = data['protocol']

        # Auto-enable simulator mode for localhost connections
        if data['ip_address'] in ['127.0.0.1', 'localhost', '::1']:
            protocol_config['simulator_mode'] = True

        # Create protocol-specific config
        if protocol == 'ETHERNET_IP':
            from oee_analytics.sparkplug.connectors.allen_bradley import AllenBradleyConfig
            config = AllenBradleyConfig(
                host=data['ip_address'],
                port=data['port'],
                timeout=data['timeout'],
                slot=protocol_config.get('slot', 0),
                plc_family=protocol_config.get('plc_family', 'ControlLogix'),
                simulator_mode=protocol_config.get('simulator_mode', False),
            )
        else:
            # For other protocols, use base config
            valid_config_fields = {
                'rack', 'slot', 'username', 'password', 'use_tls',
                'ca_cert_path', 'client_cert_path', 'client_key_path',
                'max_connections', 'connection_retry_interval', 'max_retries',
                'scan_rate_ms', 'batch_size', 'enable_subscriptions', 'simulator_mode'
            }
            filtered_config = {k: v for k, v in protocol_config.items() if k in valid_config_fields}
            config = PLCConnectionConfig(
                host=data['ip_address'],
                port=data['port'],
                timeout=data['timeout'],
                **filtered_config
            )

        # Create connector
        connector = PLCConnectorFactory.create_connector(
            plc_type=protocol,
            config=config,
            logger=logger
        )

        # Test connection
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        success = loop.run_until_complete(connector.connect())

        if success:
            health_info = loop.run_until_complete(connector.health_check())
            loop.run_until_complete(connector.disconnect())
            loop.close()

            return Response({
                'success': True,
                'message': 'Connection successful',
                'device_info': health_info
            })
        else:
            loop.close()
            return Response({
                'success': False,
                'message': 'Connection failed',
                'error': connector.last_error
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return Response({
            'success': False,
            'message': 'Connection test failed',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def discover_plcs(request):
    """
    Auto-discover PLCs at a given IP address by scanning common ports
    POST /api/plc/discover/
    Body: {ip_address, timeout}
    """
    import socket
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ip_address = request.data.get('ip_address')
    timeout = request.data.get('timeout', 1.0)

    if not ip_address:
        return Response({
            'success': False,
            'message': 'IP address is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Define common PLC ports by protocol
    port_profiles = {
        # Allen-Bradley EtherNet/IP
        **{port: {'protocol': 'ETHERNET_IP', 'name': f'Allen-Bradley Port {port}', 'slot': 0, 'plc_family': 'ControlLogix'}
           for port in range(44818, 44828)},  # Ports 44818-44827 (10 simulators)

        # Siemens OPC-UA
        4840: {'protocol': 'OPCUA', 'name': 'Siemens OPC-UA (Default)', 'security': 'None'},
        4841: {'protocol': 'OPCUA', 'name': 'Siemens S7-1500 OPC-UA', 'security': 'None'},
        4842: {'protocol': 'OPCUA', 'name': 'Siemens S7-1500 OPC-UA (Alt)', 'security': 'None'},

        # Siemens S7
        102: {'protocol': 'S7', 'name': 'Siemens S7 (ISO-TSAP)', 'rack': 0, 'slot': 1},

        # Modbus TCP
        502: {'protocol': 'MODBUS', 'name': 'Modbus TCP', 'unit_id': 1},
    }

    def check_port(port, profile):
        """Check if a port is open and responding"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip_address, port))
            sock.close()

            if result == 0:
                return {
                    'port': port,
                    'responding': True,
                    'protocol': profile['protocol'],
                    'name': profile['name'],
                    'config': {k: v for k, v in profile.items() if k not in ['protocol', 'name']}
                }
        except Exception as e:
            logger.debug(f"Port scan error {ip_address}:{port} - {e}")

        return None

    # Scan ports in parallel
    discovered = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(check_port, port, profile): port
                   for port, profile in port_profiles.items()}

        for future in as_completed(futures):
            result = future.result()
            if result:
                discovered.append(result)

    # Sort by port number
    discovered.sort(key=lambda x: x['port'])

    logger.info(f"PLC Discovery on {ip_address}: Found {len(discovered)} responding ports")

    return Response({
        'success': True,
        'ip_address': ip_address,
        'discovered': discovered,
        'total_scanned': len(port_profiles),
        'total_found': len(discovered)
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def scan_network(request):
    """
    Scan entire network subnet for PLCs (RSLinx-style discovery)
    POST /api/plc/scan-network/
    Body: {network, protocol_filter}
    """
    import socket
    import ipaddress
    from concurrent.futures import ThreadPoolExecutor, as_completed

    network = request.data.get('network', '192.168.1.0/24')
    protocol_filter = request.data.get('protocol_filter', 'all')  # all, ETHERNET_IP, OPCUA, S7, MODBUS
    timeout = request.data.get('timeout', 0.5)

    try:
        # Parse network CIDR
        net = ipaddress.ip_network(network, strict=False)
        total_hosts = net.num_addresses - 2  # Exclude network and broadcast

        if total_hosts > 1024:
            return Response({
                'success': False,
                'message': f'Network too large ({total_hosts} hosts). Maximum 1024 hosts allowed.'
            }, status=status.HTTP_400_BAD_REQUEST)

    except ValueError as e:
        return Response({
            'success': False,
            'message': f'Invalid network format: {e}'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Define ports by protocol
    protocol_ports = {
        'ETHERNET_IP': list(range(44818, 44828)) + [2222],  # Simulator ports + EtherNet/IP default
        'OPCUA': [4840, 4841, 4842],
        'S7': [102],
        'MODBUS': [502],
    }

    # Filter protocols
    if protocol_filter != 'all' and protocol_filter in protocol_ports:
        scan_ports = {protocol_filter: protocol_ports[protocol_filter]}
    else:
        scan_ports = protocol_ports

    def scan_host(ip_str, ports_to_scan):
        """Scan a single host for multiple protocols"""
        host_devices = []

        for protocol, ports in ports_to_scan.items():
            for port in ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((ip_str, port))
                    sock.close()

                    if result == 0:
                        # Normalize localhost addresses to 127.0.0.1
                        display_ip = '127.0.0.1' if ip_str.startswith('127.') else ip_str

                        device = {
                            'ip_address': display_ip,
                            'port': port,
                            'protocol': protocol,
                            'responding': True,
                            'device_info': {}
                        }

                        # Try to get device identity
                        if protocol == 'ETHERNET_IP':
                            device_info = get_ethernet_ip_identity(ip_str, port, timeout)
                            if device_info:
                                device['device_info'] = device_info
                                device['name'] = f"{device_info.get('product_name', 'Allen-Bradley Device')}"
                            else:
                                device['name'] = f'Allen-Bradley PLC (Port {port})'
                        elif protocol == 'OPCUA':
                            device['name'] = f'OPC-UA Server (Port {port})'
                        elif protocol == 'S7':
                            device['name'] = 'Siemens S7 PLC'
                        elif protocol == 'MODBUS':
                            device['name'] = 'Modbus TCP Device'

                        host_devices.append(device)
                        # Don't break - check all ports for multiple devices

                except Exception as e:
                    logger.debug(f"Scan error {ip_str}:{port} - {e}")
                    continue

        return host_devices

    # Scan network in parallel
    discovered_devices = []
    hosts_scanned = 0

    with ThreadPoolExecutor(max_workers=50) as executor:
        # Skip network address and broadcast
        hosts = [str(ip) for ip in list(net.hosts())]

        futures = {executor.submit(scan_host, host, scan_ports): host for host in hosts}

        for future in as_completed(futures):
            hosts_scanned += 1
            devices = future.result()
            if devices:
                discovered_devices.extend(devices)

    logger.info(f"Network scan {network}: Found {len(discovered_devices)} devices in {hosts_scanned} hosts")

    return Response({
        'success': True,
        'network': network,
        'total_hosts_scanned': hosts_scanned,
        'devices_found': len(discovered_devices),
        'devices': discovered_devices
    })


def get_ethernet_ip_identity(ip, port, timeout):
    """
    Get EtherNet/IP device identity using CIP protocol
    This is a simplified version - real implementation would use full CIP stack
    """
    import socket

    try:
        # EtherNet/IP List Identity command
        # This is a simplified implementation
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))

        # Send List Identity request (0x63)
        list_identity = bytes([
            0x63, 0x00,  # Command: List Identity
            0x00, 0x00,  # Length
            0x00, 0x00, 0x00, 0x00,  # Session handle
            0x00, 0x00, 0x00, 0x00,  # Status
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # Sender context
            0x00, 0x00, 0x00, 0x00   # Options
        ])

        sock.send(list_identity)
        response = sock.recv(1024)
        sock.close()

        if len(response) > 28:
            # Parse response (simplified)
            return {
                'product_name': 'Allen-Bradley PLC',
                'vendor': 'Rockwell Automation',
                'device_type': 'ControlLogix/CompactLogix',
                'revision': 'Unknown',
                'serial': 'Unknown'
            }
    except:
        pass

    return None


@api_view(['POST'])
@permission_classes([AllowAny])
def discover_tags_standalone(request):
    """
    Discover tags from PLC (standalone endpoint for wizard)
    POST /api/plc/discover-tags/
    Body: {ip_address, port, protocol, protocol_config}
    """
    import asyncio
    from oee_analytics.sparkplug.connectors.base import PLCConnectorFactory

    data = request.data
    protocol = data.get('protocol', 'ETHERNET_IP')

    try:
        # Auto-enable simulator mode for localhost
        protocol_config = data.get('protocol_config', {})
        if data['ip_address'] in ['127.0.0.1', 'localhost', '::1']:
            protocol_config['simulator_mode'] = True

        # Create protocol-specific config
        if protocol == 'ETHERNET_IP':
            from oee_analytics.sparkplug.connectors.allen_bradley import AllenBradleyConfig
            config = AllenBradleyConfig(
                host=data['ip_address'],
                port=data['port'],
                timeout=data.get('timeout', 5.0),
                slot=protocol_config.get('slot', 0),
                plc_family=protocol_config.get('plc_family', 'ControlLogix'),
                simulator_mode=protocol_config.get('simulator_mode', False),
            )
        else:
            from oee_analytics.sparkplug.connectors.base import PLCConnectionConfig
            config = PLCConnectionConfig(
                host=data['ip_address'],
                port=data['port'],
                timeout=data.get('timeout', 5.0),
            )

        # Create connector
        connector = PLCConnectorFactory.create_connector(protocol, config)

        # Run async operations in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Connect to PLC
            connected = loop.run_until_complete(connector.connect())

            if not connected:
                return Response({
                    'success': False,
                    'message': 'Failed to connect to PLC for tag discovery'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Discover tags
            discovered_tags = loop.run_until_complete(connector.discover_tags())

            # Disconnect
            loop.run_until_complete(connector.disconnect())

            # Convert tags to dict format
            tags_data = []
            for tag in discovered_tags:
                tags_data.append({
                    'name': tag.name,
                    'address': tag.address,
                    'data_type': tag.data_type,
                    'description': tag.description or '',
                    'units': tag.units or '',
                })

            return Response({
                'success': True,
                'tags': tags_data,
                'tags_found': len(tags_data),
                'message': f'Discovered {len(tags_data)} tags from PLC'
            })

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Tag discovery failed: {str(e)}")
        return Response({
            'success': False,
            'message': f'Tag discovery failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
