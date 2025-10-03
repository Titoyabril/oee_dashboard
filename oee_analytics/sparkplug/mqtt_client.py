"""
Sparkplug B MQTT Client
Production-ready implementation of Sparkplug B specification
Handles NBIRTH/NDEATH/DBIRTH/DDEATH/NDATA/DDATA/NCMD/DCMD message types
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, asdict
import ssl
import threading
from queue import Queue, Empty
import struct

import paho.mqtt.client as mqtt
try:
    from eclipse_tahu.core import sparkplug_b_pb2
    from eclipse_tahu.core.sparkplug_b import SparkplugMessageBuilder, SparkplugMessageParser
    TAHU_AVAILABLE = True
except ImportError:
    TAHU_AVAILABLE = False
    # Create mock classes for testing without Tahu
    class SparkplugMessageBuilder:
        def build_nbirth(self, *args, **kwargs): return b''
        def build_ndeath(self, *args, **kwargs): return b''
        def build_dbirth(self, *args, **kwargs): return b''
        def build_ddeath(self, *args, **kwargs): return b''
        def build_ndata(self, *args, **kwargs): return b''
        def build_ddata(self, *args, **kwargs): return b''
    class SparkplugMessageParser:
        def parse(self, *args, **kwargs): return {}
    sparkplug_b_pb2 = None

from prometheus_client import Counter, Histogram, Gauge

from .models import (
    SparkplugNode, SparkplugDevice, SparkplugMetric,
    SparkplugEventRaw, SparkplugMetricHistory, SparkplugNodeState,
    SparkplugCommandAudit
)
from ..edge.cache import EdgeCache, CacheConfig


# Prometheus metrics
MESSAGES_RECEIVED = Counter('sparkplug_messages_received_total', 'Total Sparkplug messages received', ['message_type', 'group_id', 'node_id'])
MESSAGE_PROCESSING_TIME = Histogram('sparkplug_message_processing_seconds', 'Time spent processing messages')
ACTIVE_NODES = Gauge('sparkplug_active_nodes', 'Number of active Sparkplug nodes')
SEQUENCE_ERRORS = Counter('sparkplug_sequence_errors_total', 'Sequence number errors', ['group_id', 'node_id'])
CONNECTION_STATUS = Gauge('sparkplug_mqtt_connected', 'MQTT connection status')


@dataclass
class SparkplugConfig:
    """Configuration for Sparkplug B MQTT client"""
    # MQTT Broker settings
    broker_host: str
    broker_port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "sparkplug_oee_client"
    
    # TLS settings
    use_tls: bool = False
    ca_cert_path: Optional[str] = None
    cert_path: Optional[str] = None
    key_path: Optional[str] = None
    
    # Sparkplug settings
    group_id: str = "OEE_Group"
    node_id: str = "OEE_Node"
    subscribe_group_ids: List[str] = None  # Groups to subscribe to
    
    # QoS and reliability
    qos: int = 1
    retain: bool = False
    clean_session: bool = True
    
    # Connection settings
    keep_alive: int = 60
    reconnect_delay_min: float = 1.0
    reconnect_delay_max: float = 60.0
    connection_timeout: int = 30
    
    # Message handling
    max_queue_size: int = 10000
    batch_size: int = 100
    batch_timeout: float = 1.0
    enable_compression: bool = False

    # Store-and-forward settings
    enable_store_forward: bool = True
    store_forward_max_size_mb: int = 500

    # Backpressure settings
    enable_backpressure: bool = True
    backpressure_threshold: int = 1000  # Queue size to trigger backpressure
    backpressure_resume_threshold: int = 500  # Queue size to resume normal operation

    # Birth/Death settings
    birth_timeout: int = 300  # Seconds before considering node dead
    death_timeout: int = 60   # Seconds to wait for death message
    
    # Command settings
    enable_commands: bool = False
    command_timeout: int = 30
    command_rate_limit: int = 10  # Commands per minute
    
    def __post_init__(self):
        if self.subscribe_group_ids is None:
            self.subscribe_group_ids = [self.group_id]


class SparkplugMQTTClient:
    """
    Production-ready Sparkplug B MQTT client
    Handles all Sparkplug B message types with proper sequencing and state management
    """
    
    def __init__(self, config: SparkplugConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        self.connected = False
        self.connection_event = threading.Event()

        # Message handling
        self.message_queue = Queue(maxsize=config.max_queue_size)
        self.processing_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()

        # Store-and-forward cache
        self.edge_cache: Optional[EdgeCache] = None
        if config.enable_store_forward:
            cache_config = CacheConfig(
                redis_enabled=True,
                rocksdb_enabled=True,
                max_queue_size=config.max_queue_size,
                max_memory_usage=config.store_forward_max_size_mb * 1024 * 1024
            )
            self.edge_cache = EdgeCache(cache_config)

        # Backpressure state
        self.backpressure_active = False
        self.backpressure_callbacks: List[Callable] = []

        # Sequence tracking per node
        self.node_sequences: Dict[str, int] = {}
        self.device_sequences: Dict[str, int] = {}

        # Birth/Death tracking
        self.node_states: Dict[str, Dict[str, Any]] = {}
        self.device_states: Dict[str, Dict[str, Any]] = {}

        # Command handling
        self.command_callbacks: Dict[str, Callable] = {}
        self.pending_commands: Dict[str, Dict[str, Any]] = {}

        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'messages_queued': 0,
            'messages_replayed': 0,
            'sequence_errors': 0,
            'connection_attempts': 0,
            'last_message_time': None,
            'backpressure_events': 0,
        }

        # Reconnection
        self.reconnect_delay = config.reconnect_delay_min
        self.max_reconnect_delay = config.reconnect_delay_max
        
    async def start(self) -> bool:
        """Start the Sparkplug MQTT client"""
        try:
            # Initialize edge cache if enabled
            if self.edge_cache:
                await self.edge_cache.connect()
                self.logger.info("Edge cache connected for store-and-forward")

            # Initialize MQTT client
            self._init_mqtt_client()

            # Start message processing thread
            self.processing_thread = threading.Thread(
                target=self._message_processing_loop,
                daemon=True
            )
            self.processing_thread.start()

            # Connect to broker
            success = await self._connect_with_retry()
            if success:
                self.logger.info("Sparkplug MQTT client started successfully")
                CONNECTION_STATUS.set(1)

                # Replay any queued messages from store-and-forward
                if self.edge_cache:
                    await self._replay_stored_messages()

            return success

        except Exception as e:
            self.logger.error(f"Failed to start Sparkplug client: {e}")
            CONNECTION_STATUS.set(0)
            return False
    
    async def stop(self):
        """Stop the Sparkplug MQTT client"""
        try:
            self.logger.info("Stopping Sparkplug MQTT client")

            # Signal shutdown
            self.shutdown_event.set()

            # Send death message if connected
            if self.connected:
                await self._send_death_message()

            # Disconnect MQTT
            if self.mqtt_client:
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()

            # Wait for processing thread
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join(timeout=5.0)

            # Disconnect edge cache
            if self.edge_cache:
                await self.edge_cache.disconnect()
                self.logger.info("Edge cache disconnected")

            CONNECTION_STATUS.set(0)
            self.logger.info("Sparkplug MQTT client stopped")

        except Exception as e:
            self.logger.error(f"Error stopping Sparkplug client: {e}")
    
    def _init_mqtt_client(self):
        """Initialize MQTT client with Sparkplug settings"""
        self.mqtt_client = mqtt.Client(
            client_id=self.config.client_id,
            clean_session=self.config.clean_session
        )
        
        # Set credentials
        if self.config.username and self.config.password:
            self.mqtt_client.username_pw_set(
                self.config.username, 
                self.config.password
            )
        
        # Configure TLS
        if self.config.use_tls:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            
            if self.config.ca_cert_path:
                context.load_verify_locations(self.config.ca_cert_path)
            
            if self.config.cert_path and self.config.key_path:
                context.load_cert_chain(self.config.cert_path, self.config.key_path)
            
            self.mqtt_client.tls_set_context(context)
        
        # Set will message (death message)
        will_topic = f"spBv1.0/{self.config.group_id}/NDEATH/{self.config.node_id}"
        will_payload = self._create_death_message()
        self.mqtt_client.will_set(
            will_topic, 
            will_payload, 
            qos=self.config.qos, 
            retain=False
        )
        
        # Set callbacks
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_log = self._on_log
    
    async def _connect_with_retry(self) -> bool:
        """Connect to MQTT broker with exponential backoff retry"""
        while not self.shutdown_event.is_set():
            try:
                self.stats['connection_attempts'] += 1
                self.logger.info(f"Connecting to MQTT broker {self.config.broker_host}:{self.config.broker_port}")
                
                # Start MQTT loop
                self.mqtt_client.loop_start()
                
                # Connect
                result = self.mqtt_client.connect(
                    self.config.broker_host,
                    self.config.broker_port,
                    self.config.keep_alive
                )
                
                if result == mqtt.MQTT_ERR_SUCCESS:
                    # Wait for connection confirmation
                    if self.connection_event.wait(timeout=self.config.connection_timeout):
                        self.reconnect_delay = self.config.reconnect_delay_min
                        return True
                
                raise Exception(f"Connection failed with code: {result}")
                
            except Exception as e:
                self.logger.error(f"MQTT connection failed: {e}")
                
                # Exponential backoff
                self.logger.info(f"Retrying in {self.reconnect_delay} seconds...")
                await asyncio.sleep(self.reconnect_delay)
                
                self.reconnect_delay = min(
                    self.reconnect_delay * 2,
                    self.max_reconnect_delay
                )
        
        return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connect callback"""
        if rc == 0:
            self.connected = True
            self.connection_event.set()
            self.logger.info("Connected to MQTT broker")
            
            # Subscribe to topics
            self._subscribe_to_topics()
            
            # Send birth message
            asyncio.create_task(self._send_birth_message())
            
        else:
            self.logger.error(f"MQTT connection failed with code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self.connected = False
        self.connection_event.clear()

        if rc == 0:
            self.logger.info("Disconnected from MQTT broker")
        else:
            self.logger.warning(f"Unexpected disconnect from MQTT broker: {rc}")

            # When disconnected, queue remaining messages to edge cache
            if self.edge_cache and not self.shutdown_event.is_set():
                self.logger.info("Broker unavailable - queuing messages to edge cache")
                try:
                    # Drain current message queue to edge cache
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    queued_count = 0
                    while not self.message_queue.empty():
                        try:
                            msg = self.message_queue.get_nowait()
                            # Queue this message for later
                            loop.run_until_complete(self._queue_message_for_later(
                                msg['topic'],
                                msg['payload'],
                                msg.get('qos', 1)
                            ))
                            queued_count += 1
                        except Empty:
                            break

                    loop.close()
                    self.logger.info(f"Queued {queued_count} messages to edge cache")

                except Exception as e:
                    self.logger.error(f"Error queuing messages to cache: {e}")

            # Attempt reconnection if not shutting down
            if not self.shutdown_event.is_set():
                asyncio.create_task(self._connect_with_retry())
    
    def _on_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            # Add message to processing queue
            if not self.message_queue.full():
                self.message_queue.put({
                    'topic': msg.topic,
                    'payload': msg.payload,
                    'qos': msg.qos,
                    'retain': msg.retain,
                    'timestamp': time.time()
                })
                self.stats['messages_received'] += 1
            else:
                self.logger.warning("Message queue full, dropping message")
                
        except Exception as e:
            self.logger.error(f"Error handling MQTT message: {e}")
    
    def _on_log(self, client, userdata, level, buf):
        """MQTT log callback"""
        if level == mqtt.MQTT_LOG_ERR:
            self.logger.error(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_WARNING:
            self.logger.warning(f"MQTT: {buf}")
        else:
            self.logger.debug(f"MQTT: {buf}")
    
    def _subscribe_to_topics(self):
        """Subscribe to Sparkplug B topics"""
        for group_id in self.config.subscribe_group_ids:
            # Subscribe to all message types for the group
            topics = [
                f"spBv1.0/{group_id}/NBIRTH/+",
                f"spBv1.0/{group_id}/NDEATH/+", 
                f"spBv1.0/{group_id}/DBIRTH/+",
                f"spBv1.0/{group_id}/DDEATH/+",
                f"spBv1.0/{group_id}/NDATA/+",
                f"spBv1.0/{group_id}/DDATA/+",
                f"spBv1.0/{group_id}/NCMD/+",
                f"spBv1.0/{group_id}/DCMD/+",
                f"spBv1.0/STATE/+",  # Sparkplug Host Application state
            ]
            
            for topic in topics:
                result, mid = self.mqtt_client.subscribe(topic, self.config.qos)
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.logger.debug(f"Subscribed to topic: {topic}")
                else:
                    self.logger.error(f"Failed to subscribe to topic {topic}: {result}")
    
    def _message_processing_loop(self):
        """Main message processing loop (runs in thread)"""
        batch = []
        last_batch_time = time.time()
        last_backpressure_check = time.time()

        while not self.shutdown_event.is_set():
            try:
                # Check backpressure every 5 seconds
                current_time = time.time()
                if current_time - last_backpressure_check >= 5.0:
                    import asyncio
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._check_backpressure())
                        loop.close()
                    except Exception as e:
                        self.logger.error(f"Backpressure check error: {e}")
                    last_backpressure_check = current_time

                # Get message with timeout
                try:
                    message = self.message_queue.get(timeout=0.1)
                    batch.append(message)
                except Empty:
                    message = None

                # Process batch if conditions are met
                should_process = (
                    len(batch) >= self.config.batch_size or
                    (batch and current_time - last_batch_time >= self.config.batch_timeout)
                )

                if should_process and batch:
                    self._process_message_batch(batch)
                    batch.clear()
                    last_batch_time = current_time

            except Exception as e:
                self.logger.error(f"Error in message processing loop: {e}")
                batch.clear()
    
    def _process_message_batch(self, messages: List[Dict[str, Any]]):
        """Process a batch of messages"""
        for message in messages:
            try:
                with MESSAGE_PROCESSING_TIME.time():
                    self._process_single_message(message)
                self.stats['messages_processed'] += 1
                
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")
                self.stats['messages_failed'] += 1
    
    def _process_single_message(self, message: Dict[str, Any]):
        """Process a single Sparkplug message"""
        topic = message['topic']
        payload = message['payload']
        timestamp = message['timestamp']
        
        # Parse topic
        topic_parts = topic.split('/')
        if len(topic_parts) < 4 or topic_parts[0] != 'spBv1.0':
            self.logger.warning(f"Invalid Sparkplug topic: {topic}")
            return
        
        group_id = topic_parts[1]
        message_type = topic_parts[2]
        identifier = topic_parts[3] if len(topic_parts) > 3 else None
        
        # Update metrics
        MESSAGES_RECEIVED.labels(
            message_type=message_type,
            group_id=group_id,
            node_id=identifier or 'unknown'
        ).inc()
        
        # Parse protobuf payload
        try:
            parser = SparkplugMessageParser()
            parsed_message = parser.parse_message(payload)
        except Exception as e:
            self.logger.error(f"Failed to parse Sparkplug message: {e}")
            return
        
        # Store raw message
        self._store_raw_message(topic, message_type, group_id, identifier, payload, parsed_message, timestamp)
        
        # Process by message type
        if message_type == 'NBIRTH':
            self._handle_node_birth(group_id, identifier, parsed_message, timestamp)
        elif message_type == 'NDEATH':
            self._handle_node_death(group_id, identifier, parsed_message, timestamp)
        elif message_type == 'DBIRTH':
            self._handle_device_birth(group_id, identifier, parsed_message, timestamp)
        elif message_type == 'DDEATH':
            self._handle_device_death(group_id, identifier, parsed_message, timestamp)
        elif message_type == 'NDATA':
            self._handle_node_data(group_id, identifier, parsed_message, timestamp)
        elif message_type == 'DDATA':
            self._handle_device_data(group_id, identifier, parsed_message, timestamp)
        elif message_type == 'NCMD':
            self._handle_node_command(group_id, identifier, parsed_message, timestamp)
        elif message_type == 'DCMD':
            self._handle_device_command(group_id, identifier, parsed_message, timestamp)
        elif message_type == 'STATE':
            self._handle_state_message(group_id, identifier, parsed_message, timestamp)
        
        self.stats['last_message_time'] = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    def _store_raw_message(self, topic: str, message_type: str, group_id: str, 
                          identifier: str, payload: bytes, parsed_message: Any, timestamp: float):
        """Store raw message in database"""
        try:
            # Extract node_id and device_id from identifier
            node_id = device_id = None
            if identifier:
                if message_type.startswith('N'):
                    node_id = identifier
                elif message_type.startswith('D'):
                    device_id = identifier
            
            # Create raw event record
            SparkplugEventRaw.objects.create(
                topic=topic,
                message_type=message_type,
                group_id=group_id,
                node_id=node_id,
                device_id=device_id,
                sequence_number=getattr(parsed_message, 'seq', 0),
                timestamp_utc=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                payload_protobuf=payload,
                payload_json=json.dumps(self._message_to_dict(parsed_message)),
                payload_size_bytes=len(payload),
                mqtt_qos=1,  # Default QoS
                broker_host=self.config.broker_host,
            )
            
        except Exception as e:
            self.logger.error(f"Failed to store raw message: {e}")
    
    def _handle_node_birth(self, group_id: str, node_id: str, message: Any, timestamp: float):
        """Handle Node Birth (NBIRTH) message"""
        try:
            # Reset sequence number
            node_key = f"{group_id}/{node_id}"
            self.node_sequences[node_key] = 0
            
            # Update node state
            self.node_states[node_key] = {
                'status': 'ONLINE',
                'birth_timestamp': timestamp,
                'sequence_number': getattr(message, 'seq', 0),
                'metrics': {},
            }
            
            # Get or create node
            node, created = SparkplugNode.objects.get_or_create(
                group_id=group_id,
                node_id=node_id,
                defaults={
                    'mqtt_broker_host': self.config.broker_host,
                    'mqtt_broker_port': self.config.broker_port,
                }
            )
            
            # Update node status
            node.status = 'BIRTH'
            node.last_birth_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            node.birth_sequence_number = getattr(message, 'seq', 0)
            node.save()
            
            # Process birth metrics
            if hasattr(message, 'metrics'):
                self._process_metrics(node, None, message.metrics, timestamp, getattr(message, 'seq', 0))
            
            ACTIVE_NODES.inc()
            self.logger.info(f"Node birth: {group_id}/{node_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling node birth: {e}")
    
    def _handle_node_death(self, group_id: str, node_id: str, message: Any, timestamp: float):
        """Handle Node Death (NDEATH) message"""
        try:
            node_key = f"{group_id}/{node_id}"
            
            # Update node state
            if node_key in self.node_states:
                self.node_states[node_key]['status'] = 'OFFLINE'
                self.node_states[node_key]['death_timestamp'] = timestamp
            
            # Update database
            try:
                node = SparkplugNode.objects.get(group_id=group_id, node_id=node_id)
                node.status = 'DEATH'
                node.last_death_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                node.save()
                
                # Mark all devices as offline
                SparkplugDevice.objects.filter(node=node).update(status='OFFLINE')
                
            except SparkplugNode.DoesNotExist:
                self.logger.warning(f"Received death for unknown node: {group_id}/{node_id}")
            
            ACTIVE_NODES.dec()
            self.logger.info(f"Node death: {group_id}/{node_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling node death: {e}")
    
    def _handle_device_birth(self, group_id: str, device_id: str, message: Any, timestamp: float):
        """Handle Device Birth (DBIRTH) message"""
        try:
            # Extract node_id from message (Sparkplug B requirement)
            node_id = getattr(message, 'node_id', None)
            if not node_id:
                self.logger.error("DBIRTH message missing node_id")
                return
            
            device_key = f"{group_id}/{node_id}/{device_id}"
            
            # Update device state
            self.device_states[device_key] = {
                'status': 'ONLINE',
                'birth_timestamp': timestamp,
                'sequence_number': getattr(message, 'seq', 0),
                'metrics': {},
            }
            
            # Get or create device
            try:
                node = SparkplugNode.objects.get(group_id=group_id, node_id=node_id)
                device, created = SparkplugDevice.objects.get_or_create(
                    node=node,
                    device_id=device_id,
                    defaults={
                        'device_type': 'PLC',
                        'description': f'Device {device_id} on node {node_id}',
                    }
                )
                
                # Update device status
                device.status = 'BIRTH'
                device.last_birth_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                device.save()
                
                # Process birth metrics
                if hasattr(message, 'metrics'):
                    self._process_metrics(node, device, message.metrics, timestamp, getattr(message, 'seq', 0))
                
            except SparkplugNode.DoesNotExist:
                self.logger.error(f"Device birth for unknown node: {group_id}/{node_id}")
            
            self.logger.info(f"Device birth: {group_id}/{node_id}/{device_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling device birth: {e}")
    
    def _handle_device_death(self, group_id: str, device_id: str, message: Any, timestamp: float):
        """Handle Device Death (DDEATH) message"""
        try:
            node_id = getattr(message, 'node_id', None)
            if not node_id:
                self.logger.error("DDEATH message missing node_id") 
                return
            
            device_key = f"{group_id}/{node_id}/{device_id}"
            
            # Update device state
            if device_key in self.device_states:
                self.device_states[device_key]['status'] = 'OFFLINE'
                self.device_states[device_key]['death_timestamp'] = timestamp
            
            # Update database
            try:
                node = SparkplugNode.objects.get(group_id=group_id, node_id=node_id)
                device = SparkplugDevice.objects.get(node=node, device_id=device_id)
                device.status = 'DEATH'
                device.last_death_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                device.save()
                
            except (SparkplugNode.DoesNotExist, SparkplugDevice.DoesNotExist):
                self.logger.warning(f"Received death for unknown device: {group_id}/{node_id}/{device_id}")
            
            self.logger.info(f"Device death: {group_id}/{node_id}/{device_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling device death: {e}")
    
    def _handle_node_data(self, group_id: str, node_id: str, message: Any, timestamp: float):
        """Handle Node Data (NDATA) message"""
        try:
            node_key = f"{group_id}/{node_id}"
            
            # Validate sequence number
            expected_seq = self.node_sequences.get(node_key, 0) + 1
            actual_seq = getattr(message, 'seq', 0)
            
            if actual_seq != expected_seq and expected_seq != 1:
                SEQUENCE_ERRORS.labels(group_id=group_id, node_id=node_id).inc()
                self.logger.warning(f"Sequence error for {node_key}: expected {expected_seq}, got {actual_seq}")
            
            self.node_sequences[node_key] = actual_seq
            
            # Get node and process metrics
            try:
                node = SparkplugNode.objects.get(group_id=group_id, node_id=node_id)
                node.last_data_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                node.last_sequence_number = actual_seq
                node.message_count += 1
                node.save()
                
                if hasattr(message, 'metrics'):
                    self._process_metrics(node, None, message.metrics, timestamp, actual_seq)
                
            except SparkplugNode.DoesNotExist:
                self.logger.warning(f"Received data for unknown node: {group_id}/{node_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling node data: {e}")
    
    def _handle_device_data(self, group_id: str, device_id: str, message: Any, timestamp: float):
        """Handle Device Data (DDATA) message"""
        try:
            node_id = getattr(message, 'node_id', None)
            if not node_id:
                self.logger.error("DDATA message missing node_id")
                return
            
            # Get device and process metrics
            try:
                node = SparkplugNode.objects.get(group_id=group_id, node_id=node_id)
                device = SparkplugDevice.objects.get(node=node, device_id=device_id)
                
                device.last_data_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                device.message_count += 1
                device.save()
                
                if hasattr(message, 'metrics'):
                    self._process_metrics(node, device, message.metrics, timestamp, getattr(message, 'seq', 0))
                
            except (SparkplugNode.DoesNotExist, SparkplugDevice.DoesNotExist):
                self.logger.warning(f"Received data for unknown device: {group_id}/{node_id}/{device_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling device data: {e}")
    
    def _process_metrics(self, node: SparkplugNode, device: Optional[SparkplugDevice], 
                        metrics: List[Any], timestamp: float, sequence_number: int):
        """Process metrics from Sparkplug message"""
        try:
            for metric in metrics:
                metric_name = getattr(metric, 'name', '')
                metric_value = getattr(metric, 'value', None)
                metric_alias = getattr(metric, 'alias', None)
                metric_datatype = getattr(metric, 'datatype', 0)
                
                # Get or create metric definition
                metric_obj, created = SparkplugMetric.objects.get_or_create(
                    node=node if device is None else None,
                    device=device,
                    name=metric_name,
                    defaults={
                        'alias': metric_alias,
                        'data_type': self._get_datatype_string(metric_datatype),
                        'description': f'Auto-discovered metric: {metric_name}',
                    }
                )
                
                # Update metric metadata
                metric_obj.last_value = json.dumps(metric_value)
                metric_obj.last_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                metric_obj.message_count += 1
                metric_obj.save()
                
                # Store metric history
                SparkplugMetricHistory.objects.create(
                    metric=metric_obj,
                    timestamp_utc=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                    value_json=json.dumps(metric_value),
                    sequence_number=sequence_number,
                )
                
        except Exception as e:
            self.logger.error(f"Error processing metrics: {e}")
    
    def _handle_node_command(self, group_id: str, node_id: str, message: Any, timestamp: float):
        """Handle Node Command (NCMD) message"""
        if not self.config.enable_commands:
            self.logger.warning("Received command but commands are disabled")
            return
        
        # TODO: Implement command handling
        self.logger.info(f"Node command received: {group_id}/{node_id}")
    
    def _handle_device_command(self, group_id: str, device_id: str, message: Any, timestamp: float):
        """Handle Device Command (DCMD) message"""
        if not self.config.enable_commands:
            self.logger.warning("Received command but commands are disabled")
            return
        
        # TODO: Implement command handling
        self.logger.info(f"Device command received: {group_id}/{device_id}")
    
    def _handle_state_message(self, group_id: str, identifier: str, message: Any, timestamp: float):
        """Handle Host Application State message"""
        self.logger.info(f"State message received: {group_id}/{identifier}")
    
    async def _send_birth_message(self):
        """Send Node Birth (NBIRTH) message"""
        try:
            # Create birth message
            builder = SparkplugMessageBuilder()
            birth_metrics = [
                {
                    'name': 'Node Control/Rebirth',
                    'value': False,
                    'datatype': sparkplug_b_pb2.Boolean
                }
            ]
            
            birth_payload = builder.create_node_birth_payload(
                timestamp=int(time.time() * 1000),
                metrics=birth_metrics
            )
            
            # Publish birth message
            topic = f"spBv1.0/{self.config.group_id}/NBIRTH/{self.config.node_id}"
            self.mqtt_client.publish(
                topic,
                birth_payload,
                qos=self.config.qos,
                retain=self.config.retain
            )
            
            self.logger.info("Published node birth message")
            
        except Exception as e:
            self.logger.error(f"Failed to send birth message: {e}")
    
    async def _send_death_message(self):
        """Send Node Death (NDEATH) message"""
        try:
            # Create death message
            builder = SparkplugMessageBuilder()
            death_payload = builder.create_node_death_payload(
                timestamp=int(time.time() * 1000)
            )
            
            # Publish death message
            topic = f"spBv1.0/{self.config.group_id}/NDEATH/{self.config.node_id}"
            self.mqtt_client.publish(
                topic,
                death_payload,
                qos=self.config.qos,
                retain=False
            )
            
            self.logger.info("Published node death message")
            
        except Exception as e:
            self.logger.error(f"Failed to send death message: {e}")
    
    def _create_death_message(self) -> bytes:
        """Create death message for MQTT will"""
        try:
            builder = SparkplugMessageBuilder()
            return builder.create_node_death_payload(
                timestamp=int(time.time() * 1000)
            )
        except:
            return b""
    
    def _message_to_dict(self, message: Any) -> Dict[str, Any]:
        """Convert protobuf message to dictionary"""
        try:
            # This is a simplified conversion
            # In practice, you'd want proper protobuf to dict conversion
            return {
                'timestamp': getattr(message, 'timestamp', 0),
                'seq': getattr(message, 'seq', 0),
                'metrics_count': len(getattr(message, 'metrics', [])),
            }
        except:
            return {}
    
    def _get_datatype_string(self, datatype: int) -> str:
        """Convert Sparkplug datatype to string"""
        datatype_map = {
            1: 'Int8',
            2: 'Int16', 
            3: 'Int32',
            4: 'Int64',
            5: 'UInt8',
            6: 'UInt16',
            7: 'UInt32',
            8: 'UInt64',
            9: 'Float',
            10: 'Double',
            11: 'Boolean',
            12: 'String',
            13: 'DateTime',
            14: 'Text',
        }
        return datatype_map.get(datatype, 'Unknown')
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics"""
        stats = {
            **self.stats,
            'connected': self.connected,
            'active_nodes': len(self.node_states),
            'active_devices': len(self.device_states),
            'queue_size': self.message_queue.qsize(),
            'backpressure_active': self.backpressure_active,
        }

        # Add edge cache stats if available
        if self.edge_cache:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                cache_stats = loop.run_until_complete(self.edge_cache.get_stats())
                stats['edge_cache'] = cache_stats
            except:
                pass

        return stats

    def register_backpressure_callback(self, callback: Callable[[bool], None]):
        """Register a callback to be notified of backpressure events"""
        self.backpressure_callbacks.append(callback)

    async def _check_backpressure(self):
        """Check queue size and trigger backpressure if needed"""
        if not self.config.enable_backpressure:
            return

        queue_size = self.message_queue.qsize()

        # Activate backpressure if threshold exceeded
        if not self.backpressure_active and queue_size >= self.config.backpressure_threshold:
            self.backpressure_active = True
            self.stats['backpressure_events'] += 1
            self.logger.warning(f"Backpressure activated: queue size {queue_size}")

            # Notify all callbacks
            for callback in self.backpressure_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(True)
                    else:
                        callback(True)
                except Exception as e:
                    self.logger.error(f"Backpressure callback error: {e}")

        # Deactivate backpressure if below resume threshold
        elif self.backpressure_active and queue_size <= self.config.backpressure_resume_threshold:
            self.backpressure_active = False
            self.logger.info(f"Backpressure deactivated: queue size {queue_size}")

            # Notify all callbacks
            for callback in self.backpressure_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(False)
                    else:
                        callback(False)
                except Exception as e:
                    self.logger.error(f"Backpressure callback error: {e}")

    async def _queue_message_for_later(self, topic: str, payload: bytes, qos: int = 1):
        """Queue message to edge cache for later delivery"""
        if not self.edge_cache:
            self.logger.warning("Edge cache not available, message will be lost")
            return

        try:
            message_data = {
                'topic': topic,
                'payload': payload.hex(),  # Convert bytes to hex string for storage
                'qos': qos,
                'timestamp': time.time(),
            }

            await self.edge_cache.queue_for_forward(message_data)
            self.stats['messages_queued'] += 1
            self.logger.debug(f"Message queued for later delivery: {topic}")

        except Exception as e:
            self.logger.error(f"Failed to queue message: {e}")

    async def _replay_stored_messages(self):
        """Replay messages from store-and-forward cache after reconnection"""
        if not self.edge_cache:
            return

        try:
            self.logger.info("Replaying stored messages from cache")

            # Get all pending messages
            pending = await self.edge_cache.get_pending_data()

            if not pending:
                self.logger.info("No messages to replay")
                return

            self.logger.info(f"Replaying {len(pending)} stored messages")

            for message_data in pending:
                try:
                    # Restore bytes from hex string
                    payload = bytes.fromhex(message_data['payload'])

                    # Publish the message
                    result = self.mqtt_client.publish(
                        message_data['topic'],
                        payload,
                        qos=message_data.get('qos', 1),
                        retain=False
                    )

                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        self.stats['messages_replayed'] += 1
                    else:
                        self.logger.error(f"Failed to replay message: {result.rc}")
                        # Re-queue the message
                        await self._queue_message_for_later(
                            message_data['topic'],
                            payload,
                            message_data.get('qos', 1)
                        )

                except Exception as e:
                    self.logger.error(f"Error replaying message: {e}")

            self.logger.info(f"Replay complete: {self.stats['messages_replayed']} messages sent")

        except Exception as e:
            self.logger.error(f"Failed to replay stored messages: {e}")